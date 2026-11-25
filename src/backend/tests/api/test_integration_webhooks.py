import json
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from uuid import uuid4

import httpx
import pytest
from alembic import command
from celery.result import denied_join_result
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import IntegrationEvent, WebhookEndpoint
from app.services.integration_events import (
    enqueue_integration_event,
    validate_payload,
    verify_webhook_signature,
    webhook_signature,
)
from app.workers import integration_webhooks
from app.workers.celery_app import celery_app, create_celery_app
from tests.conftest import migration_config

NOW = datetime(2026, 11, 25, 0, tzinfo=UTC)
PATH = "/webhook/hr-ats/test"
SECRET = "synthetic-key-for-tests-only-0123456789"


def configured(origin="http://127.0.0.1:5678"):
    return Settings(
        _env_file=None,
        app_env="test",
        integration_webhooks_enabled=True,
        integration_webhook_origin=origin,
        integration_webhook_secret=SECRET,
    )


def create_endpoint(session):
    endpoint = WebhookEndpoint(id=uuid4(), path=PATH, enabled=True)
    session.add(endpoint)
    session.flush()
    return endpoint


def enqueue(session, endpoint_id, *, key=None, count=2, now=NOW):
    return enqueue_integration_event(
        session,
        endpoint_id=endpoint_id,
        event_type="task.overdue_summary",
        dedupe_key=key or uuid4(),
        payload={"overdue_count": count},
        now=now,
    )


def test_signature_interoperability_and_rejection():
    body = b'{"version":1}'
    timestamp = str(int(NOW.timestamp()))
    signature = webhook_signature(SECRET, timestamp, PATH, body)
    assert signature == "v1=9c152587698054bb8e948e5a81b899ff221d539b0e24086c821d9887bee867f3"
    assert verify_webhook_signature(SECRET, timestamp, PATH, body, signature, NOW)
    assert not verify_webhook_signature(SECRET, timestamp, PATH, body + b" ", signature, NOW)
    assert not verify_webhook_signature(SECRET, timestamp, PATH + "/other", body, signature, NOW)
    assert not verify_webhook_signature("different", timestamp, PATH, body, signature, NOW)
    assert not verify_webhook_signature(
        SECRET, timestamp, PATH, body, signature, NOW + timedelta(seconds=301)
    )


@pytest.mark.parametrize(
    ("event_type", "payload"),
    [
        ("future.event", {}),
        ("integration.test", {"name": "Ứng viên giả"}),
        ("task.overdue_summary", {}),
        ("task.overdue_summary", {"overdue_count": 0}),
        ("task.overdue_summary", {"overdue_count": True}),
        ("task.overdue_summary", {"overdue_count": "2"}),
        ("task.overdue_summary", {"overdue_count": 2, "cv": "Nội dung giả"}),
        ("task.overdue_summary", {"overdue_count": 2, "candidate_id": "synthetic"}),
    ],
)
def test_strict_payload_rejects_personal_and_unexpected_fields(event_type, payload):
    with pytest.raises(ValueError, match="^Invalid integration event metadata$"):
        validate_payload(event_type, payload)


def test_insert_is_idempotent_and_does_not_commit(db_session):
    endpoint_id = create_endpoint(db_session).id
    db_session.commit()
    key = uuid4()
    event_id = enqueue(db_session, endpoint_id, key=key)
    assert enqueue(db_session, endpoint_id, key=key, count=9) == event_id
    event = db_session.scalars(select(IntegrationEvent)).one()
    assert event.payload == {"overdue_count": 2}
    db_session.rollback()
    assert db_session.scalars(select(IntegrationEvent)).all() == []


@pytest.mark.parametrize("failure", ["timeout", "redirect", "wrong_id", "oversized"])
def test_retries_preserve_payload_and_stop_after_matching_ack(db_session, monkeypatch, failure):
    endpoint_id = create_endpoint(db_session).id
    event_id = enqueue(db_session, endpoint_id)
    requests = []

    def handle(request):
        requests.append(request)
        if len(requests) == 1:
            if failure == "timeout":
                raise httpx.ReadTimeout("synthetic", request=request)
            if failure == "redirect":
                return httpx.Response(307, headers={"location": "https://example.invalid"})
            if failure == "oversized":
                return httpx.Response(200, stream=httpx.ByteStream(b" " * 1025))
        reply_id = "wrong-id" if len(requests) == 1 else str(event_id)
        body = json.dumps({"received": True, "event_id": reply_id}).encode()
        return httpx.Response(200, stream=httpx.ByteStream(body))

    @contextmanager
    def stream(method, url, *, content, headers, timeout, follow_redirects, trust_env):
        assert not trust_env
        with (
            httpx.Client(transport=httpx.MockTransport(handle), timeout=timeout) as client,
            client.stream(
                method, url, content=content, headers=headers, follow_redirects=follow_redirects
            ) as response,
        ):
            yield response

    monkeypatch.setattr(integration_webhooks.httpx, "stream", stream)
    settings = configured()
    assert integration_webhooks.deliver_next(db_session, settings, NOW)
    assert not integration_webhooks.deliver_next(db_session, settings, NOW + timedelta(seconds=59))
    assert integration_webhooks.deliver_next(db_session, settings, NOW + timedelta(seconds=60))
    assert not integration_webhooks.deliver_next(db_session, settings, NOW + timedelta(days=1))
    assert requests[0].content == requests[1].content
    for request, now in zip(requests, (NOW, NOW + timedelta(seconds=60)), strict=True):
        assert verify_webhook_signature(
            SECRET,
            request.headers["X-HR-ATS-Timestamp"],
            request.url.path,
            request.content,
            request.headers["X-HR-ATS-Signature"],
            now,
        )
    assert json.loads(requests[0].content) == {
        "event_id": str(event_id),
        "event_type": "task.overdue_summary",
        "version": 1,
        "data": {"overdue_count": 2},
    }


def test_disabled_endpoint_and_retry_limit(db_session, monkeypatch):
    endpoint = create_endpoint(db_session)
    event_id = enqueue(db_session, endpoint.id)
    endpoint.enabled = False
    db_session.flush()
    monkeypatch.setattr(integration_webhooks, "send_event", lambda *_: False)
    settings = configured()
    assert enqueue(db_session, endpoint.id) is None
    assert not integration_webhooks.deliver_next(db_session, settings, NOW)
    endpoint.enabled = True
    db_session.flush()
    for seconds in (0, 60, 360, 1260):
        assert integration_webhooks.deliver_next(
            db_session, settings, NOW + timedelta(seconds=seconds)
        )
    assert not integration_webhooks.deliver_next(db_session, settings, NOW + timedelta(days=1))
    event = db_session.get_one(IntegrationEvent, event_id)
    assert event.attempts == 4
    assert event.delivered_at is None
    assert event.failed_at == NOW + timedelta(seconds=1260)


def test_parallel_worker_skips_locked_delivery(empty_engine, monkeypatch):
    with empty_engine.begin() as connection:
        config = migration_config()
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    settings = configured()
    with Session(empty_engine) as first, Session(empty_engine) as second:
        endpoint_id = create_endpoint(first).id
        enqueue(first, endpoint_id)
        first.commit()

        def send(*_):
            assert not integration_webhooks.deliver_next(second, settings, NOW)
            return True

        monkeypatch.setattr(integration_webhooks, "send_event", send)
        assert integration_webhooks.deliver_next(first, settings, NOW)
        assert not integration_webhooks.deliver_next(second, settings, NOW)


def test_temporary_outage_recovers_even_after_the_initial_retry_window(db_session, monkeypatch):
    event_id = enqueue(db_session, create_endpoint(db_session).id)
    settings = configured()
    monkeypatch.setattr(integration_webhooks, "send_event", lambda *_: "retry")
    for seconds in (0, 60, 360, 1260, 2160):
        assert integration_webhooks.deliver_next(
            db_session, settings, NOW + timedelta(seconds=seconds)
        )
    event = db_session.get_one(IntegrationEvent, event_id)
    assert event.id == event_id
    assert event.failed_at is None
    assert event.next_attempt_at == NOW + timedelta(seconds=3060)
    monkeypatch.setattr(integration_webhooks, "send_event", lambda *_: True)
    assert integration_webhooks.deliver_next(db_session, settings, event.next_attempt_at)
    assert db_session.get_one(IntegrationEvent, event_id).delivered_at is not None


def test_celery_delivers_signed_event_to_loopback(db_session, monkeypatch):
    requests = []

    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            valid = verify_webhook_signature(
                SECRET,
                self.headers["X-HR-ATS-Timestamp"],
                self.path,
                body,
                self.headers["X-HR-ATS-Signature"],
                datetime.now(UTC),
            )
            requests.append(valid)
            event_id = json.loads(body)["event_id"]
            self.send_response(200 if valid else 403)
            self.end_headers()
            self.wfile.write(json.dumps({"received": valid, "event_id": event_id}).encode())

    assert (
        "deliver-integration-webhooks"
        not in create_celery_app(Settings(_env_file=None)).conf.beat_schedule
    )
    endpoint_id = create_endpoint(db_session).id
    event_id = enqueue(db_session, endpoint_id)
    db_session.commit()

    @contextmanager
    def worker_session():
        yield db_session

    monkeypatch.setattr(integration_webhooks, "worker_session", worker_session)
    with ThreadingHTTPServer(("127.0.0.1", 0), Receiver) as server, denied_join_result():
        settings = configured(f"http://127.0.0.1:{server.server_port}")
        assert (
            create_celery_app(settings).conf.beat_schedule["deliver-integration-webhooks"][
                "schedule"
            ]
            == 60
        )
        monkeypatch.setattr(integration_webhooks, "get_settings", lambda: settings)
        thread = Thread(target=server.serve_forever)
        thread.start()
        try:
            deliver = celery_app.tasks["deliver_integration_webhooks"]
            deliver.apply(throw=True)
            deliver.apply(throw=True)
        finally:
            server.shutdown()
            thread.join()
    assert requests == [True]
    assert db_session.get_one(IntegrationEvent, event_id).delivered_at is not None


@pytest.mark.parametrize(
    "origin",
    [
        "http://example.invalid",
        "https://example.invalid/path",
        "https://example.invalid?",
        "https://user@example.invalid",
        "https://example.invalid\\@target.invalid",
    ],
)
def test_worker_config_requires_one_trusted_origin(origin):
    with pytest.raises(ValidationError):
        configured(origin)
