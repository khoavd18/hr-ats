from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.redis import get_redis
from app.main import create_app
from tests.auth_helpers import sign_in


def test_health_checks_real_postgresql_and_redis(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok", "redis": "ok"}


@pytest.mark.parametrize("failed_dependency", ["db", "redis", "both", "redis_false"])
def test_dependency_failures_return_safe_503(app: FastAPI, client: TestClient, failed_dependency):
    session = Mock(spec=Session)
    redis_client = Mock(spec=Redis)
    redis_client.ping.return_value = True
    if failed_dependency in {"db", "both"}:
        session.execute.side_effect = OperationalError(None, None, Exception("synthetic-db-detail"))
    if failed_dependency in {"redis", "both"}:
        redis_client.ping.side_effect = RedisConnectionError("synthetic-redis-detail")
    if failed_dependency == "redis_false":
        redis_client.ping.return_value = False
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_redis] = lambda: redis_client
    response = client.get("/api/v1/health")
    assert response.status_code == 503
    assert response.json() == {
        "error": {"code": "SERVICE_UNAVAILABLE", "message": "Dịch vụ tạm thời không khả dụng."}
    }
    assert "synthetic" not in response.text
    session.execute.assert_called_once()
    redis_client.ping.assert_called_once()


def test_public_configuration_exposes_only_the_configured_label(app, client, account) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(hiring_unit_label="Phòng tuyển dụng")
    assert sign_in(client).status_code == 200
    response = client.get("/api/v1/config/public")
    assert response.status_code == 200
    assert response.json() == {"hiring_unit_label": "Phòng tuyển dụng"}


def test_cors_accepts_only_the_configured_origin(client: TestClient) -> None:
    allowed = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    denied = client.options(
        "/api/v1/health",
        headers={"Origin": "https://example.invalid", "Access-Control-Request-Method": "GET"},
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert allowed.headers["access-control-allow-credentials"] == "true"
    assert denied.status_code == 400
    assert denied.json() == {
        "error": {"code": "CORS_REJECTED", "message": "Yêu cầu không được phép."}
    }
    assert "access-control-allow-origin" not in denied.headers


def test_openapi_and_docs_are_available_in_dev(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json").json()
    assert "/api/v1/health" in schema["paths"]
    assert "/api/v1/config/public" in schema["paths"]
    responses = schema["paths"]["/api/v1/health"]["get"]["responses"]
    for status in ("404", "405", "422", "500", "503"):
        assert responses[status]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/ErrorResponse"
        }


def test_production_does_not_expose_docs_or_openapi() -> None:
    application = create_app(
        Settings(app_env="prod", secret_key="synthetic-production-key-for-tests-only")
    )
    with TestClient(application) as client:
        for path in ("/docs", "/redoc", "/openapi.json"):
            response = client.get(path)
            assert response.status_code == 404
            assert response.json()["error"]["code"] == "NOT_FOUND"
