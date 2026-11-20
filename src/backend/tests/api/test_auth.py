from datetime import timedelta
from uuid import uuid4

import jwt
import pytest

from app.core import security
from app.core.config import Settings, get_settings
from app.models.users import User
from tests.auth_helpers import PASSWORD, csrf_headers, sign_in


def test_login_normalizes_email_and_sets_cookie_attributes(client, account, caplog):
    response = sign_in(client, " AUTH-USER@EXAMPLE.INVALID ")
    assert response.status_code == 200
    assert response.json()["id"] == str(account.id)
    assert "password_hash" not in response.text
    assert "auth_version" not in response.text
    cookies = response.headers.get_list("set-cookie")
    for name in ("access_token", "refresh_token"):
        cookie = next(value for value in cookies if value.startswith(name + "="))
        assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Path=/" in cookie
    access = security.decode_token(client.cookies["access_token"], "access", get_settings())
    refresh = security.decode_token(client.cookies["refresh_token"], "refresh", get_settings())
    assert access["exp"] - access["iat"] == 1800
    assert refresh["exp"] - refresh["iat"] == 604800
    assert client.get("/api/v1/auth/me").status_code == 200
    assert account.last_login_at is not None
    assert account.password_hash.startswith("$argon2id$")
    assert PASSWORD not in caplog.text
    assert account.email not in caplog.text
    assert client.cookies["access_token"] not in caplog.text


def test_wrong_unknown_and_inactive_credentials_have_same_response(client, account, db_session):
    wrong = sign_in(client, password="wrong-synthetic")
    missing = sign_in(client, email="missing@example.invalid")
    account.is_active = False
    db_session.commit()
    inactive = sign_in(client)
    assert wrong.status_code == missing.status_code == inactive.status_code == 401
    assert wrong.json() == missing.json() == inactive.json()


def test_fifth_failure_locks_for_15_minutes_and_unlocks_after_expiry(
    client, account, db_session, monkeypatch
):
    now = security.utcnow()
    monkeypatch.setattr(security, "utcnow", lambda: now)
    for _ in range(4):
        assert sign_in(client, password="wrong-synthetic").status_code == 401
    assert sign_in(client, password="wrong-synthetic").status_code == 423
    db_session.refresh(account)
    assert account.failed_login_attempts == 5
    assert account.locked_until == now + timedelta(minutes=15)
    assert sign_in(client).status_code == 423
    monkeypatch.setattr(security, "utcnow", lambda: now + timedelta(minutes=15))
    assert sign_in(client).status_code == 200
    assert account.failed_login_attempts == 0 and account.locked_until is None


def test_success_resets_failures_and_new_login_revokes_previous_session(client, account):
    assert sign_in(client, password="wrong-synthetic").status_code == 401
    assert sign_in(client).status_code == 200
    old_access = client.cookies["access_token"]
    assert account.failed_login_attempts == 0
    assert sign_in(client).status_code == 200
    client.cookies.set("access_token", old_access)
    assert client.get("/api/v1/auth/me").status_code == 401


def test_refresh_rotates_and_rejects_replay(client, account):
    sign_in(client)
    old_access = client.cookies["access_token"]
    old_refresh = client.cookies["refresh_token"]
    old_csrf = client.cookies["csrf_token"]
    response = client.post("/api/v1/auth/refresh", headers=csrf_headers(client))
    assert response.status_code == 200
    assert client.cookies["access_token"] != old_access
    assert client.cookies["refresh_token"] != old_refresh
    assert client.cookies["csrf_token"] != old_csrf
    assert client.get("/api/v1/auth/me").status_code == 200
    client.cookies.clear()
    client.cookies.update(
        {"access_token": old_access, "refresh_token": old_refresh, "csrf_token": old_csrf}
    )
    assert (
        client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": old_csrf}).status_code == 401
    )
    assert client.get("/api/v1/auth/me").status_code == 401


def test_logout_revokes_copied_tokens_and_clears_cookies(client, account):
    sign_in(client)
    copied = dict(client.cookies)
    client.cookies.delete("access_token")
    response = client.post("/api/v1/auth/logout", headers=csrf_headers(client))
    assert response.status_code == 204
    assert not dict(client.cookies)
    client.cookies.update(copied)
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.post("/api/v1/auth/refresh", headers=csrf_headers(client)).status_code == 401


@pytest.mark.parametrize("path", ["login", "logout", "refresh", "change-password"])
def test_auth_mutations_require_csrf(client, account, path):
    sign_in(client)
    response = client.post("/api/v1/auth/" + path, json={})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_INVALID"


def test_csrf_rejects_mismatch_forgery_other_session_and_wrong_origin(client, account):
    sign_in(client)
    current = client.cookies["csrf_token"]
    assert client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": "wrong"}).status_code == 403
    assert (
        client.post(
            "/api/v1/auth/refresh",
            headers={"X-CSRF-Token": current, "Origin": "https://example.invalid"},
        ).status_code
        == 403
    )
    for token in ("forged.forged", security.new_csrf(get_settings())):
        client.cookies.clear()
        client.cookies.update(
            {
                "csrf_token": token,
                "refresh_token": security.encode_token(account, "refresh", current, get_settings()),
            },
        )
        assert (
            client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": token}).status_code == 403
        )


def test_change_password_verifies_old_password_and_revokes_session(client, account):
    sign_in(client)
    old_cookies = dict(client.cookies)
    body = {"current_password": "wrong-synthetic", "new_password": "new-synthetic-password"}
    assert (
        client.post(
            "/api/v1/auth/change-password", json=body, headers=csrf_headers(client)
        ).status_code
        == 400
    )
    body["current_password"] = PASSWORD
    assert (
        client.post(
            "/api/v1/auth/change-password", json=body, headers=csrf_headers(client)
        ).status_code
        == 204
    )
    client.cookies.update(old_cookies)
    assert client.get("/api/v1/auth/me").status_code == 401
    assert sign_in(client).status_code == 401
    assert sign_in(client, password=body["new_password"]).status_code == 200


@pytest.mark.parametrize(
    "fault", ["expired", "wrong_type", "wrong_signature", "missing_claim", "missing_user"]
)
def test_invalid_access_tokens_are_401(client, account, fault):
    settings = get_settings()
    token = security.encode_token(account, "access", "synthetic-csrf", settings)
    payload = jwt.decode(
        token, settings.secret_key.get_secret_value(), algorithms=["HS256"], audience="hr-ats-web"
    )
    if fault == "expired":
        payload["exp"] = 1
    elif fault == "wrong_type":
        payload["type"] = "refresh"
    elif fault == "missing_claim":
        del payload["ver"]
    elif fault == "missing_user":
        payload["sub"] = str(uuid4())
    key = (
        "another-synthetic-key-for-tests-only"
        if fault == "wrong_signature"
        else settings.secret_key.get_secret_value()
    )
    client.cookies.set("access_token", jwt.encode(payload, key, algorithm="HS256"))
    assert client.get("/api/v1/auth/me").status_code == 401


def test_production_cookies_are_secure():
    from fastapi import Response

    from app.api.auth import set_session

    user = User(id=uuid4(), auth_version=0)
    response = Response()
    set_session(
        response,
        user,
        Settings(app_env="prod", secret_key="synthetic-production-key-for-tests-only"),
    )
    assert all("Secure" in value for value in response.headers.getlist("set-cookie"))


def test_config_requires_authentication(client, account):
    assert client.get("/api/v1/config/public").status_code == 401
    sign_in(client)
    assert client.get("/api/v1/config/public").status_code == 200


def test_login_issuance_cannot_adopt_a_later_sessions_version(client, account, monkeypatch):
    from app.services import auth

    original_login = auth.login

    def login_then_another_session(session, email, password):
        user, version = original_login(session, email, password)
        # A later login/refresh commits before the first response has encoded its JWTs.
        user.auth_version += 1
        session.commit()
        return user, version

    monkeypatch.setattr(auth, "login", login_then_another_session)
    assert sign_in(client).status_code == 200
    claims = security.decode_token(client.cookies["access_token"], "access", get_settings())
    assert claims["ver"] + 1 == account.auth_version
    assert client.get("/api/v1/auth/me").status_code == 401
