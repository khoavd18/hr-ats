"""Run the outbox on PostgreSQL with a synthetic webhook receiver."""

import json
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.core.config import Settings
from app.models import Job, OverdueWebhookEvent, Task, UserRole
from app.models.enums import TaskStatus
from app.workers import overdue_webhook
from app.workers.celery_app import celery_app, create_celery_app
from tests.api.test_pipeline import seed_records

NOW = datetime(2026, 11, 20, 1, tzinfo=UTC)


def test_summary_counts_only_open_visible_past_deadlines_and_queues_once(db_session, account):
    records = seed_records(db_session, account)
    account.role = UserRole.recruiter
    other = records.other
    hidden_job = db_session.get_one(Job, records.job.id)
    hidden_job.owner_id = other.id

    def add(**fields):
        db_session.add(Task(title="Việc giả", created_by=account.id, **fields))

    add(assignee_id=account.id, due_at=NOW - timedelta(seconds=1))
    add(assignee_id=account.id, due_at=NOW, status=TaskStatus.doing)
    add(assignee_id=account.id, due_at=NOW + timedelta(hours=1))
    add(assignee_id=account.id)
    add(assignee_id=account.id, due_at=NOW - timedelta(days=1), deleted_at=NOW)
    add(assignee_id=account.id, due_at=NOW - timedelta(days=1), status=TaskStatus.cancelled)
    add(
        assignee_id=account.id,
        due_at=NOW - timedelta(days=1),
        status=TaskStatus.done,
        completed_at=NOW,
    )
    add(assignee_id=account.id, due_at=NOW - timedelta(days=1), job_id=hidden_job.id)
    add(assignee_id=other.id, due_at=NOW - timedelta(days=1))
    db_session.commit()

    overdue_webhook.queue_summary(db_session, account.id, NOW)
    overdue_webhook.queue_summary(db_session, account.id, NOW + timedelta(minutes=1))

    event = db_session.scalars(select(OverdueWebhookEvent)).one()
    assert event.overdue_count == 1
    assert event.reminder_day.isoformat() == "2026-11-20"


@pytest.mark.parametrize("failure", ["timeout", "redirect", "500", "not-json", "wrong-id"])
def test_retries_unchanged_payload_until_receiver_confirms(
    db_session, account, monkeypatch, failure
):
    settings = Settings(
        _env_file=None,
        n8n_overdue_enabled=True,
        n8n_overdue_webhook_url="http://127.0.0.1:5678/webhook/hr-ats/task-overdue",
        n8n_overdue_webhook_key="synthetic-test-key",
        n8n_overdue_user_id=account.id,
    )
    db_session.add(
        Task(
            title="Việc giả",
            created_by=account.id,
            assignee_id=account.id,
            due_at=NOW - timedelta(minutes=1),
        )
    )
    db_session.commit()
    overdue_webhook.queue_summary(db_session, account.id, NOW)
    event = db_session.scalars(select(OverdueWebhookEvent)).one()
    event_id = str(event.id)
    sent = []

    def receiver(request):
        assert request.method == "POST"
        assert str(request.url) == settings.n8n_overdue_webhook_url
        assert request.headers["X-HR-ATS-Key"] == "synthetic-test-key"
        sent.append(json.loads(request.content))
        if len(sent) == 1:
            if failure == "timeout":
                raise httpx.ReadTimeout("synthetic", request=request)
            if failure == "redirect":
                return httpx.Response(307, headers={"Location": "http://127.0.0.1:9999"})
            if failure == "500":
                return httpx.Response(500)
            if failure == "not-json":
                return httpx.Response(200, text="synthetic")
            return httpx.Response(200, json={"received": True, "event_id": "wrong-id"})
        return httpx.Response(200, json={"received": True, "event_id": event_id})

    def post(url, *, headers, json, timeout, follow_redirects, trust_env):
        with httpx.Client(
            transport=httpx.MockTransport(receiver),
            timeout=timeout,
            follow_redirects=follow_redirects,
            trust_env=trust_env,
        ) as client:
            return client.post(url, headers=headers, json=json)

    monkeypatch.setattr(overdue_webhook.httpx, "post", post)
    overdue_webhook.deliver_summary(db_session, settings, NOW)
    assert event.delivered_at is None and event.attempts == 1
    assert event.next_attempt_at == NOW + timedelta(minutes=1)
    overdue_webhook.deliver_summary(db_session, settings, NOW + timedelta(seconds=59))
    assert len(sent) == 1
    retry_at = NOW + timedelta(minutes=1)
    overdue_webhook.deliver_summary(db_session, settings, retry_at)
    overdue_webhook.deliver_summary(db_session, settings, retry_at)
    assert event.delivered_at == retry_at and event.attempts == 2
    assert (
        sent
        == [
            {
                "event_id": event_id,
                "event_type": "task.overdue_summary",
                "version": 1,
                "overdue_count": 1,
            }
        ]
        * 2
    )


def test_schedule_is_opt_in_and_uses_default_queue(account):
    common = {
        "n8n_overdue_webhook_url": "http://127.0.0.1:5678/webhook/hr-ats/task-overdue",
        "n8n_overdue_webhook_key": "synthetic-test-key",
        "n8n_overdue_user_id": account.id,
    }
    inactive = create_celery_app(Settings(_env_file=None, **common))
    active = create_celery_app(Settings(_env_file=None, n8n_overdue_enabled=True, **common))
    try:
        assert "queue-overdue-webhook" not in inactive.conf.beat_schedule
        assert "deliver-overdue-webhook" not in inactive.conf.beat_schedule
        assert active.conf.timezone == "Asia/Ho_Chi_Minh"
        entry = active.conf.beat_schedule["queue-overdue-webhook"]
        assert entry["schedule"].hour == {8} and entry["schedule"].minute == {0}
        assert active.conf.beat_schedule["deliver-overdue-webhook"]["schedule"] == 60.0
        for task in ("queue_overdue_webhook", "deliver_overdue_webhook"):
            assert active.amqp.router.route({}, task)["queue"].name == "default"
    finally:
        active.close()
        inactive.close()
        celery_app.set_current()


def test_expired_summary_does_not_send_or_block_today(db_session, account, monkeypatch):
    midnight = datetime(2026, 11, 20, 17, tzinfo=UTC)
    expired = OverdueWebhookEvent(
        id=uuid4(),
        user_id=account.id,
        reminder_day=date(2026, 11, 20),
        overdue_count=3,
        next_attempt_at=midnight,
    )
    today = OverdueWebhookEvent(
        id=uuid4(),
        user_id=account.id,
        reminder_day=date(2026, 11, 21),
        overdue_count=1,
        next_attempt_at=midnight + timedelta(seconds=1),
    )
    db_session.add_all([expired, today])
    db_session.commit()
    settings = Settings(_env_file=None, n8n_overdue_user_id=account.id)
    sent = []

    def post(url, *, json, **kwargs):
        sent.append(json)
        return httpx.Response(200, json={"received": True, "event_id": json["event_id"]})

    monkeypatch.setattr(overdue_webhook.httpx, "post", post)
    overdue_webhook.deliver_summary(db_session, settings, midnight)
    assert sent == []
    overdue_webhook.deliver_summary(db_session, settings, midnight + timedelta(seconds=1))
    assert [message["event_id"] for message in sent] == [str(today.id)]
    assert today.delivered_at is not None
    assert expired.delivered_at is None and expired.attempts == 0


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:5678/webhook-test/hr-ats/task-overdue",
        "http://example.invalid/webhook/hr-ats/task-overdue",
        "https://example.invalid/webhook/hr-ats/task-overdue?key=synthetic",
        "https://example.invalid:100000/webhook/hr-ats/task-overdue",
    ],
)
def test_enabled_settings_require_production_url_without_secrets(url):
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            n8n_overdue_enabled=True,
            n8n_overdue_webhook_url=url,
            n8n_overdue_webhook_key="synthetic-test-key",
            n8n_overdue_user_id=uuid4(),
        )


def test_registered_tasks_deliver_from_db_to_local_http_receiver(db_session, account, monkeypatch):
    requests = []

    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            event = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append((self.path, self.headers["X-HR-ATS-Key"], event))
            reply = json.dumps({"received": True, "event_id": event["event_id"]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(reply)))
            self.end_headers()
            self.wfile.write(reply)

    db_session.add(
        Task(
            title="Việc giả",
            created_by=account.id,
            assignee_id=account.id,
            due_at=datetime.now(UTC) - timedelta(days=1),
        )
    )
    db_session.commit()

    @contextmanager
    def worker_session():
        yield db_session

    monkeypatch.setattr(overdue_webhook, "worker_session", worker_session)
    with ThreadingHTTPServer(("127.0.0.1", 0), Receiver) as server:
        settings = Settings(
            _env_file=None,
            n8n_overdue_enabled=True,
            n8n_overdue_webhook_url=f"http://127.0.0.1:{server.server_port}/webhook/test",
            n8n_overdue_webhook_key="synthetic-test-key",
            n8n_overdue_user_id=account.id,
        )
        monkeypatch.setattr(overdue_webhook, "get_settings", lambda: settings)
        thread = Thread(target=server.serve_forever)
        thread.start()
        try:
            celery_app.tasks["queue_overdue_webhook"].apply().get()
            account.is_active = False
            db_session.commit()
            celery_app.tasks["deliver_overdue_webhook"].apply().get()
            assert requests == []

            account.is_active = True
            db_session.commit()
            celery_app.tasks["deliver_overdue_webhook"].apply().get()
            celery_app.tasks["deliver_overdue_webhook"].apply().get()
        finally:
            server.shutdown()
            thread.join()

    event = db_session.scalars(select(OverdueWebhookEvent)).one()
    assert event.delivered_at is not None
    assert requests == [
        (
            "/webhook/test",
            "synthetic-test-key",
            {
                "event_id": str(event.id),
                "event_type": "task.overdue_summary",
                "version": 1,
                "overdue_count": 1,
            },
        )
    ]
