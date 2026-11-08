import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_request_log_uses_route_template_without_parameters_or_query(
    app: FastAPI, client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    @app.get("/test/items/{item_id}")
    def item(item_id: str) -> dict:
        return {"ok": True}

    response = client.get("/test/items/synthetic-private-path?body=synthetic-private-query")
    assert response.status_code == 200
    records = [record for record in caplog.records if record.name == "app.http"]
    assert len(records) == 1
    record = records[0]
    assert record.method == "GET"
    assert record.route == "/test/items/{item_id}"
    assert record.status == 200
    assert record.duration_ms >= 0
    assert "synthetic-private" not in str(record.__dict__)


@pytest.mark.parametrize("status", [404, 500])
def test_request_log_records_errors_without_raw_unmatched_paths(
    app: FastAPI, client: TestClient, caplog: pytest.LogCaptureFixture, status: int
) -> None:
    @app.get("/test/failure")
    def fail() -> None:
        raise RuntimeError("synthetic-private-exception")

    path = "/test/failure" if status == 500 else "/synthetic-private-unmatched"
    response = client.get(path)
    assert response.status_code == status
    record = next(record for record in caplog.records if record.name == "app.http")
    assert record.status == status
    assert record.route == ("/test/failure" if status == 500 else "[unmatched]")
    assert "synthetic-private" not in str(record.__dict__)
