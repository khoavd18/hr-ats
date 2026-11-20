from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.models.users import User, UserRole
from tests.auth_helpers import PASSWORD, csrf_headers, sign_in


@pytest.fixture
def recruiter(db_session):
    user = User(
        email="recruiter@example.invalid",
        full_name="Người dùng giả",
        role=UserRole.recruiter,
        password_hash=hash_password(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.mark.parametrize("role", [UserRole.recruiter, UserRole.lead])
def test_non_admin_cannot_list_create_or_modify_users(client, recruiter, db_session, role):
    recruiter.role = role
    db_session.commit()
    sign_in(client, recruiter.email)
    assert client.get("/api/v1/users").status_code == 403
    data = {
        "email": "new@example.invalid",
        "full_name": "Giả",
        "role": "admin",
        "password": PASSWORD,
    }
    assert client.post("/api/v1/users", json=data, headers=csrf_headers(client)).status_code == 403
    assert (
        client.patch(
            f"/api/v1/users/{recruiter.id}", json={"role": "admin"}, headers=csrf_headers(client)
        ).status_code
        == 403
    )


def test_admin_can_list_create_change_role_and_disable(client, account, recruiter, db_session):
    sign_in(client)
    response = client.get("/api/v1/users?page=1&page_size=1")
    assert response.status_code == 200
    assert response.json()["total"] == 2 and len(response.json()["items"]) == 1
    assert "password_hash" not in response.text and "auth_version" not in response.text
    data = {
        "email": "NEW@EXAMPLE.INVALID",
        "full_name": "Tài khoản giả mới",
        "role": "lead",
        "password": PASSWORD,
    }
    created = client.post("/api/v1/users", json=data, headers=csrf_headers(client))
    assert created.status_code == 201
    assert created.json()["email"] == "new@example.invalid"
    stored = db_session.scalar(select(User).where(User.email == "new@example.invalid"))
    assert stored.password_hash.startswith("$argon2id$") and stored.password_hash != PASSWORD
    assert client.post("/api/v1/users", json=data, headers=csrf_headers(client)).status_code == 409
    changed = client.patch(
        f"/api/v1/users/{recruiter.id}", json={"role": "lead"}, headers=csrf_headers(client)
    )
    assert changed.status_code == 200 and changed.json()["role"] == "lead"
    disabled = client.patch(
        f"/api/v1/users/{recruiter.id}", json={"is_active": False}, headers=csrf_headers(client)
    )
    assert disabled.status_code == 200 and disabled.json()["is_active"] is False
    assert sign_in(client, recruiter.email).status_code == 401


def test_role_or_active_change_revokes_existing_tokens(client, account, recruiter):
    sign_in(client, recruiter.email)
    copied = dict(client.cookies)
    sign_in(client)
    assert (
        client.patch(
            f"/api/v1/users/{recruiter.id}", json={"role": "lead"}, headers=csrf_headers(client)
        ).status_code
        == 200
    )
    client.cookies.clear()
    client.cookies.update(copied)
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.post("/api/v1/auth/refresh", headers=csrf_headers(client)).status_code == 401


def test_user_mutations_require_csrf_and_prevent_self_lockout(client, account):
    sign_in(client)
    assert client.patch(f"/api/v1/users/{account.id}", json={"role": "lead"}).status_code == 403
    for data in ({"role": "lead"}, {"is_active": False}):
        assert (
            client.patch(
                f"/api/v1/users/{account.id}", json=data, headers=csrf_headers(client)
            ).status_code
            == 409
        )
    assert (
        client.patch(
            f"/api/v1/users/{uuid4()}", json={"role": "lead"}, headers=csrf_headers(client)
        ).status_code
        == 404
    )


@pytest.mark.parametrize(
    "body",
    [{"role": None}, {"is_active": None}, {"password_hash": "forbidden"}, {"role": "unknown"}],
)
def test_patch_rejects_null_unknown_and_sensitive_fields(client, account, body):
    sign_in(client)
    response = client.patch(f"/api/v1/users/{account.id}", json=body, headers=csrf_headers(client))
    assert response.status_code == 422
    assert "forbidden" not in response.text
