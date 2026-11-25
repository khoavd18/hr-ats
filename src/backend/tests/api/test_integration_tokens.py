import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.api.rate_limits import get_limit_redis
from app.core.config import get_settings
from app.models import AuditLog, IntegrationToken, Task
from app.services.integration_tokens import issue_token, revoke_token


def service_headers(db_session, account, scopes):
    token_id, token = issue_token(
        db_session, account.id, scopes, datetime.now(UTC) + timedelta(days=1)
    )
    db_session.commit()
    return token_id, {"Authorization": f"Bearer {token}"}


def test_bearer_creates_task_and_reads_only_aggregate_report(client, db_session, account):
    token_id, headers = service_headers(db_session, account, ["tasks:create", "reports:summary"])
    task = client.post("/api/v1/integrations/tasks", headers=headers, json={"title": "Việc giả"})
    assert task.status_code == 201, task.text
    assert set(task.json()) == {"task_id"}
    assert db_session.scalars(select(Task)).one().created_by == account.id
    report = client.get(
        "/api/v1/integrations/reports/summary?from=2026-11-24&to=2026-11-25", headers=headers
    )
    assert report.status_code == 200, report.text
    assert set(report.json()) == {"period", "metrics", "new_cvs_by_day"}
    token = db_session.get_one(IntegrationToken, token_id)
    assert (
        token.token_hash == hashlib.sha256(headers["Authorization"].split()[1].encode()).hexdigest()
    )
    audits = list(db_session.scalars(select(AuditLog).where(AuditLog.entity_id == token_id)))
    assert {item.action for item in audits} == {"integration.token_issued", "integration.access"}
    assert {item.details["scope"] for item in audits if item.details} == {
        "tasks:create",
        "reports:summary",
    }
    assert all(headers["Authorization"] not in str(item.details) for item in audits)


@pytest.mark.parametrize("failure", ["expired", "revoked", "inactive", "wrong_secret", "absent"])
def test_invalid_identity_is_denied(client, db_session, account, failure):
    token_id, headers = service_headers(db_session, account, ["tasks:create"])
    if failure == "expired":
        db_session.get_one(IntegrationToken, token_id).expires_at = datetime.now(UTC)
    if failure == "revoked":
        assert revoke_token(db_session, token_id)
    if failure == "inactive":
        account.is_active = False
    if failure == "wrong_secret":
        value = headers["Authorization"]
        headers["Authorization"] = value[:-1] + ("a" if value[-1] != "a" else "b")
    if failure == "absent":
        headers = {}
    db_session.commit()
    response = client.post(
        "/api/v1/integrations/tasks", headers=headers, json={"title": "Việc giả"}
    )
    assert response.status_code == 401


def test_token_cannot_access_work_requiring_another_scope(client, db_session, account):
    _, headers = service_headers(db_session, account, ["reports:summary", "cv:upload"])
    unapproved = client.post("/api/v1/integrations/cv-files", headers=headers)
    assert unapproved.status_code == 403
    task = client.post("/api/v1/integrations/tasks", headers=headers, json={"title": "Việc giả"})
    assert task.status_code == 403


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/v1/auth/me"),
        ("GET", "/api/v1/jobs"),
        ("GET", "/api/v1/cv-files/{id}/download"),
        ("POST", "/api/v1/cv-files"),
        ("GET", "/api/v1/applications/{id}"),
        ("POST", "/api/v1/applications/{id}/move"),
        ("POST", "/api/v1/email-messages/{id}/send"),
        ("GET", "/api/v1/reports/export.xlsx?from=2026-11-24&to=2026-11-25"),
        ("GET", "/api/v1/tasks"),
    ],
)
def test_bearer_is_not_a_browser_session(client, db_session, account, method, path):
    _, headers = service_headers(
        db_session, account, ["reports:summary", "tasks:create", "cv:upload"]
    )
    response = client.request(method, path.format(id=uuid4()), headers=headers)
    assert response.status_code in {401, 403}, (method, path, response.status_code)


def test_per_token_rate_limit_returns_retry_after(client, app, db_session, account):
    class RateRedis:
        def __init__(self):
            self.count = 0

        def eval(self, script, numkeys, key, seconds):
            assert "integration:" in key and seconds == 60
            self.count += 1
            return [self.count, 42]

    db = RateRedis()
    app.dependency_overrides[get_limit_redis] = lambda: db
    app.dependency_overrides[get_settings] = lambda: get_settings().model_copy(
        update={"integration_rate_limit_per_minute": 1}
    )
    _, headers = service_headers(db_session, account, ["tasks:create"])
    assert (
        client.post(
            "/api/v1/integrations/tasks", headers=headers, json={"title": "Việc giả"}
        ).status_code
        == 201
    )
    response = client.post(
        "/api/v1/integrations/tasks", headers=headers, json={"title": "Việc giả"}
    )
    assert response.status_code == 429
    assert response.headers["retry-after"] == "42"
