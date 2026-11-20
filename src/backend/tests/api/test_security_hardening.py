"""T30 controls at the HTTP boundary; all inputs are synthetic."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError

from app.api.rate_limits import get_limit_redis
from app.core.config import get_settings
from app.main import create_app
from tests.auth_helpers import csrf_headers, sign_in


@pytest.mark.parametrize("path,status", [("/missing", 404), ("/api/v1/auth/me", 401)])
def test_security_headers_cover_errors(client, path, status):
    response = client.get(path)
    assert response.status_code == status
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]


def test_headers_cover_unhandled_errors_and_cors_preflight():
    app = create_app()

    @app.get("/synthetic-failure")
    def fail():
        raise RuntimeError("synthetic private data")

    with TestClient(app, raise_server_exceptions=False) as client:
        responses = [
            client.get("/synthetic-failure"),
            client.options(
                "/api/v1/auth/login",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "POST",
                },
            ),
        ]
    assert [response.status_code for response in responses] == [500, 200]
    for response in responses:
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["Referrer-Policy"] == "no-referrer"
        assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_login_limit_counts_different_accounts_and_ignores_forwarded_header(
    client,
    app,
    account,
):
    settings = get_settings().model_copy(update={"login_rate_limit_per_minute": 2})
    app.dependency_overrides[get_settings] = lambda: settings
    for index in range(2):
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": f"missing-{index}@example.invalid",
                "password": "synthetic-password",
            },
            headers=csrf_headers(client) | {"X-Forwarded-For": f"192.0.2.{index + 1}"},
        )
        assert response.status_code == 401
    response = sign_in(client)
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMITED"
    assert 1 <= int(response.headers["Retry-After"]) <= 60
    assert response.headers["Cache-Control"] == "no-store"


def test_upload_limit_runs_before_multipart_parsing(client, app, account):
    settings = get_settings().model_copy(update={"upload_rate_limit_per_minute": 1})
    app.dependency_overrides[get_settings] = lambda: settings
    assert sign_in(client).status_code == 200
    assert client.post("/api/v1/cv-files", headers=csrf_headers(client)).status_code == 422
    response = client.post("/api/v1/cv-files", headers=csrf_headers(client))
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMITED"


def test_limiter_redis_failure_is_closed_and_has_no_details(client, app, account):
    unavailable = Mock()
    unavailable.eval.side_effect = RedisConnectionError("synthetic credential should stay private")
    app.dependency_overrides[get_limit_redis] = lambda: unavailable
    response = sign_in(client)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert "credential" not in response.text


def test_upload_batch_limit_is_an_http_413_with_security_headers(client, account, monkeypatch):
    monkeypatch.setattr("app.api.upload_parser.MAX_BATCH_BYTES", 200)
    assert sign_in(client).status_code == 200
    response = client.post(
        "/api/v1/cv-files",
        content=b"x" * 201,
        headers=csrf_headers(client) | {"Content-Type": "multipart/form-data; boundary=synthetic"},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "UPLOAD_TOO_LARGE"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_separate_api_instances_share_login_budget(account, db_session, app):
    from app.core.db import get_session

    settings = get_settings().model_copy(update={"login_rate_limit_per_minute": 1})
    app.dependency_overrides[get_settings] = lambda: settings
    other_app = create_app(settings)
    other_app.dependency_overrides[get_session] = lambda: db_session
    with TestClient(app) as first, TestClient(other_app) as second:
        assert sign_in(first).status_code == 200
        assert sign_in(second).status_code == 429
