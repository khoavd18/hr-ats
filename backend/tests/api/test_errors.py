from typing import Annotated

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException

from app.core.errors import AppError


def test_app_error_preserves_safe_code_message_and_status(app: FastAPI, client: TestClient) -> None:
    @app.get("/test/app-error")
    def fail() -> None:
        raise AppError("SYNTHETIC_CONFLICT", "Dữ liệu giả đã tồn tại.", 409)

    response = client.get("/test/app-error")
    assert response.status_code == 409
    assert response.json() == {
        "error": {"code": "SYNTHETIC_CONFLICT", "message": "Dữ liệu giả đã tồn tại."}
    }


def test_validation_errors_do_not_echo_input(app: FastAPI, client: TestClient) -> None:
    class SyntheticInput(BaseModel):
        count: Annotated[int, Field(gt=0)]

    @app.post("/test/validation")
    def validate(payload: SyntheticInput) -> dict[str, int]:
        return {"count": payload.count}

    response = client.post("/test/validation", json={"count": "synthetic-private-input"})
    assert response.status_code == 422
    assert response.json() == {
        "error": {"code": "VALIDATION_ERROR", "message": "Dữ liệu không hợp lệ."}
    }
    assert "synthetic-private-input" not in response.text


def test_unexpected_errors_do_not_leak_internal_details(app: FastAPI, client: TestClient) -> None:
    @app.get("/test/unexpected")
    def fail() -> None:
        raise RuntimeError("synthetic-private-detail")

    response = client.get("/test/unexpected")
    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "INTERNAL_ERROR", "message": "Đã có lỗi xảy ra. Vui lòng thử lại sau."}
    }
    assert "synthetic-private-detail" not in response.text


def test_http_errors_do_not_echo_exception_details(app: FastAPI, client: TestClient) -> None:
    @app.get("/test/http-error")
    def fail() -> None:
        raise HTTPException(403, "synthetic-private-detail")

    response = client.get("/test/http-error")
    assert response.status_code == 403
    assert response.json() == {
        "error": {"code": "FORBIDDEN", "message": "Bạn không có quyền thực hiện thao tác này."}
    }


def test_not_found_and_method_not_allowed_use_error_envelope(client: TestClient) -> None:
    missing = client.get("/api/v1/missing")
    wrong_method = client.post("/api/v1/health")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"
    assert wrong_method.status_code == 405
    assert wrong_method.json()["error"]["code"] == "METHOD_NOT_ALLOWED"
    assert wrong_method.headers["allow"] == "GET"


@pytest.mark.parametrize("allowed", [True, False])
def test_unexpected_errors_keep_cors_only_for_the_allowed_origin(
    app: FastAPI, client: TestClient, allowed: bool
) -> None:
    @app.get("/test/cors-error")
    def fail() -> None:
        raise RuntimeError("synthetic-private-detail")

    origin = "http://localhost:3000" if allowed else "https://example.invalid"
    response = client.get("/test/cors-error", headers={"Origin": origin})
    assert response.status_code == 500
    if allowed:
        assert response.headers["access-control-allow-origin"] == origin
        assert response.headers["access-control-allow-credentials"] == "true"
    else:
        assert "access-control-allow-origin" not in response.headers
