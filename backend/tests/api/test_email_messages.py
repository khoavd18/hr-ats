"""T23: synthetic recipients, real PostgreSQL, memory SMTP, no external network."""

import smtplib
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from celery.exceptions import Retry
from icalendar import Calendar
from sqlalchemy import func, select

from app.core.config import Settings
from app.models import Activity, EmailMessage, EmailTemplate, HiringUnit, Interview, JobMember
from app.models.enums import ActivityType, ApplicationStage, EmailStatus
from app.models.users import UserRole
from app.workers import email, tasks
from tests.api.test_pipeline import seed_records
from tests.auth_helpers import csrf_headers, sign_in

BASE = "/api/v1/email-messages"


@pytest.fixture
def records(db_session, account, monkeypatch):
    data = seed_records(db_session, account)
    data.candidate.email = "synthetic-t23@example.invalid"
    data.application.stage = ApplicationStage.submitted
    data.interview = Interview(
        application_id=data.application.id,
        round=1,
        scheduled_at=datetime(2026, 11, 12, 2, 30, tzinfo=UTC),
        duration_minutes=45,
        location_or_link="Phòng giả T23",
    )
    db_session.add(data.interview)
    db_session.commit()

    @contextmanager
    def session():
        yield db_session

    monkeypatch.setattr(email, "worker_session", session)
    monkeypatch.setattr(tasks, "worker_session", session)
    return data


def post(client, path, body=None):
    return client.post(path, json=body, headers=csrf_headers(client))


def template(session, key):
    return session.scalar(select(EmailTemplate).where(EmailTemplate.key == key))


def draft(client, records, **changes):
    return post(
        client,
        BASE,
        dict(
            application_id=str(records.application.id),
            to_email="synthetic-t23@example.invalid",
            subject="Thư giả T23",
            body="Nội dung giả <script>alert(1)</script> {{ candidate_name }}",
        )
        | changes,
    )


def move(client, records, stage="interview"):
    return post(client, f"/api/v1/applications/{records.application.id}/move", {"to_stage": stage})


def deliver(row, attempt=0, delivery_id=None):
    checkpoint = row.scheduled_for.isoformat() if row.scheduled_for else ""
    email.send_email_message.run(str(row.id), delivery_id or row.message_id, checkpoint, attempt)


def test_move_preview_draft_confirm_smtp_calendar_and_duplicate_delivery(
    client, account, records, db_session, email_outbox
):
    sign_in(client)
    response = move(client, records)
    assert response.status_code == 200, response.text
    suggestion = response.json()["suggested_email"]
    assert suggestion["to_email"] == records.candidate.email
    assert suggestion["has_calendar"] and "09:30" in suggestion["body"]
    assert not email_outbox
    assert db_session.scalar(select(func.count()).select_from(EmailMessage)) == 0
    data = {
        key: suggestion[key]
        for key in ("application_id", "template_id", "to_email", "subject", "body")
    }
    data["subject"] = "HR sửa tiêu đề giả"
    created = post(client, BASE, data)
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "draft" and not email_outbox
    record_id = created.json()["id"]
    row = db_session.get_one(EmailMessage, UUID(record_id))
    deliver(row, delivery_id="not-confirmed")
    assert not email_outbox
    sent = post(client, f"{BASE}/{record_id}/send")
    assert sent.status_code == 202, sent.text
    assert sent.json()["status"] == "queued"
    db_session.refresh(row)
    assert row.status == "sent" and row.message_id and row.sent_at and row.error is None
    assert len(email_outbox) == 1
    message = email_outbox[0]
    assert str(message["To"]) == records.candidate.email
    assert str(message["Subject"]) == data["subject"]
    assert str(message["Message-ID"]) == row.message_id
    assert "Chào" in message.get_body(preferencelist=("plain",)).get_content()
    (attachment,) = list(message.iter_attachments())
    assert attachment.get_filename() == "phong-van.ics"
    event = Calendar.from_ical(attachment.get_payload(decode=True)).walk("vevent")[0]
    assert event.decoded("dtstart") == records.interview.scheduled_at
    assert str(event["location"]) == records.interview.location_or_link
    assert event.decoded("dtend") - event.decoded("dtstart") == timedelta(minutes=45)
    deliver(row)
    assert post(client, f"{BASE}/{record_id}/send").status_code == 202
    assert len(email_outbox) == 1
    activities = db_session.scalars(
        select(Activity).where(Activity.type == ActivityType.email_sent)
    ).all()
    assert len(activities) == 1
    assert activities[0].payload == {"email_message_id": record_id}
    assert activities[0].actor_id == account.id
    listed = client.get(BASE, params={"application_id": str(records.application.id)}).json()
    assert listed["total"] == 1 and listed["items"][0]["status"] == "sent"


@pytest.mark.parametrize("key", ["interview_invite", "rejection", "offer", "submitted_to_unit"])
def test_no_template_path_sends_without_explicit_confirmation(
    client, account, records, db_session, email_outbox, key
):
    sign_in(client)
    row = draft(client, records, template_id=str(template(db_session, key).id))
    assert row.status_code == 201, row.text
    message = db_session.get_one(EmailMessage, UUID(row.json()["id"]))
    deliver(message)
    assert message.status == "draft" and not email_outbox
    cancelled = post(client, f"{BASE}/{message.id}/cancel")
    assert cancelled.json()["status"] == "cancelled"
    assert post(client, f"{BASE}/{message.id}/send").status_code == 409
    deliver(message)
    assert not email_outbox


def test_missing_address_missing_variables_inactive_and_submitted_recipient(
    client, account, records, db_session, email_outbox
):
    sign_in(client)
    records.candidate.email = None
    db_session.commit()
    result = move(client, records).json()
    assert result["application"]["stage"] == "interview"
    assert result["suggested_email"] is None and result["email_notice"] == "EMAIL_NO_ADDRESS"
    records.application.stage = ApplicationStage.screening
    unit = db_session.get_one(HiringUnit, records.job.hiring_unit_id)
    unit.contact_email = "synthetic-unit@example.invalid"
    db_session.commit()
    result = move(client, records, "submitted").json()
    assert result["suggested_email"]["to_email"] == unit.contact_email
    records.candidate.email = "synthetic-t23@example.invalid"
    records.application.stage = ApplicationStage.submitted
    records.interview.deleted_at = datetime.now(UTC)
    db_session.commit()
    result = move(client, records).json()
    assert (
        result["email_notice"] == "EMAIL_MISSING_INTERVIEW_TIME"
        and result["suggested_email"] is None
    )
    row = template(db_session, "rejection")
    row.is_active = False
    db_session.commit()
    preview = post(
        client,
        BASE + "/preview",
        {
            "application_id": str(records.application.id),
            "template_id": str(row.id),
        },
    )
    assert (
        preview.status_code == 422 and preview.json()["error"]["code"] == "EMAIL_TEMPLATE_INACTIVE"
    )
    assert not email_outbox


def test_literal_content_is_escaped_not_evaluated_and_unsafe_headers_rejected(
    client, account, records, email_outbox
):
    sign_in(client)
    response = draft(client, records)
    assert response.status_code == 201
    assert "&lt;script&gt;" in response.json()["body_html"]
    assert "{{ candidate_name }}" in response.json()["body_html"]
    for changes in (
        {"subject": "Hello\r\nBcc: synthetic@example.invalid"},
        {"to_email": "a@example.invalid,b@example.invalid"},
        {"to_email": "a@example.invalid\r\nBcc: b@example.invalid"},
        {"status": "queued"},
        {"message_id": "forged"},
        {"body_html": "<script>bad</script>"},
    ):
        result = draft(client, records, **changes)
        assert result.status_code == 422, result.text
        assert "Bcc" not in result.text and "<script>" not in result.text
    assert not email_outbox


def test_auth_csrf_object_scope_revocation_and_preview_for_recruiter(
    client, account, records, db_session, email_outbox
):
    assert (
        client.get(BASE, params={"application_id": str(records.application.id)}).status_code == 401
    )
    sign_in(client)
    assert client.post(BASE, json={}).status_code == 403
    account.role = UserRole.recruiter
    db_session.commit()
    choices = client.get(
        BASE + "/templates", params={"application_id": str(records.application.id)}
    )
    assert choices.status_code == 200 and len(choices.json()["items"]) == 5
    rendered = post(
        client,
        BASE + "/preview",
        {
            "application_id": str(records.application.id),
            "template_id": str(template(db_session, "interview_invite").id),
        },
    )
    assert rendered.status_code == 200 and not email_outbox
    message = draft(client, records).json()
    records.job.owner_id = records.other.id
    db_session.commit()
    for path in (BASE, BASE + "/templates"):
        assert (
            client.get(path, params={"application_id": str(records.application.id)}).status_code
            == 403
        )
    for action in ("send", "cancel"):
        assert post(client, f"{BASE}/{message['id']}/{action}").status_code == 403
    assert draft(client, records).status_code == 403
    db_session.add(JobMember(job_id=records.job.id, user_id=account.id))
    db_session.commit()
    assert post(client, f"{BASE}/{message['id']}/cancel").status_code == 200
    assert not email_outbox


def test_queue_failure_is_safe_and_retry_uses_same_draft(
    client, account, records, db_session, monkeypatch, email_outbox
):
    sign_in(client)
    message = draft(client, records).json()
    original = email.send_email_message.apply_async

    def fail(**kwargs):
        raise RuntimeError("synthetic-private@example.invalid")

    monkeypatch.setattr(email.send_email_message, "apply_async", fail)
    result = post(client, f"{BASE}/{message['id']}/send")
    assert result.status_code == 503 and "synthetic-private" not in result.text
    row = db_session.get_one(EmailMessage, UUID(message["id"]))
    assert row.status == "failed" and row.scheduled_for is None
    old_delivery = row.message_id
    monkeypatch.setattr(email.send_email_message, "apply_async", original)
    assert post(client, f"{BASE}/{message['id']}/send").status_code == 202
    assert row.status == "sent" and row.message_id != old_delivery
    assert len(email_outbox) == 1


def test_smtp_retries_exact_delays_and_final_failure_no_pii(
    client, account, records, db_session, monkeypatch, caplog
):
    sign_in(client)
    row_data = draft(client, records).json()
    monkeypatch.setattr(email.send_email_message, "apply_async", lambda **kwargs: None)
    assert post(client, f"{BASE}/{row_data['id']}/send").status_code == 202
    row = db_session.get_one(EmailMessage, UUID(row_data["id"]))

    def fail(*args):
        raise smtplib.SMTPException("synthetic-private@example.invalid confidential body")

    monkeypatch.setattr(email, "deliver", fail)
    retries = []

    def retry(**kwargs):
        retries.append(kwargs)
        return Retry()

    monkeypatch.setattr(email.send_email_message, "retry", retry)
    for attempt, expected in enumerate((60, 300, 900, None)):
        row.scheduled_for = datetime.now(UTC) - timedelta(seconds=1)
        db_session.commit()
        if expected:
            with pytest.raises(Retry):
                deliver(row, attempt)
            assert retries[-1]["countdown"] == expected
            assert retries[-1]["kwargs"]["attempt"] == attempt + 1
        else:
            deliver(row, attempt)
        assert row.status == "failed"
        assert "synthetic-private" not in row.error
    assert row.scheduled_for is None and row.sent_at is None
    assert "synthetic-private" not in caplog.text and "confidential body" not in caplog.text


def test_global_rate_limit_defers_without_consuming_smtp_attempts_then_cancel(
    client, account, records, db_session, monkeypatch, email_outbox
):
    sign_in(client)
    monkeypatch.setattr(email, "get_settings", lambda: Settings(email_rate_limit_per_hour=1))
    monkeypatch.setattr(email.send_email_message, "apply_async", lambda **kwargs: None)
    first = draft(client, records).json()
    post(client, f"{BASE}/{first['id']}/send")
    row = db_session.get_one(EmailMessage, UUID(first["id"]))
    deliver(row)
    assert len(email_outbox) == 1
    second = draft(client, records).json()
    post(client, f"{BASE}/{second['id']}/send")
    row2 = db_session.get_one(EmailMessage, UUID(second["id"]))
    monkeypatch.setattr(email.send_email_message, "retry", lambda **kwargs: Retry())
    with pytest.raises(Retry):
        deliver(row2)
    assert row2.status == "queued" and row2.scheduled_for > datetime.now(UTC)
    assert len(email_outbox) == 1
    post(client, f"{BASE}/{row2.id}/cancel")
    deliver(row2)
    assert len(email_outbox) == 1


def test_duplicate_old_attempt_cannot_restart_retry_cycle(
    client, account, records, db_session, monkeypatch
):
    sign_in(client)
    published = []
    monkeypatch.setattr(
        email.send_email_message, "apply_async", lambda **kw: published.append(kw["args"])
    )
    message = draft(client, records).json()
    post(client, f"{BASE}/{message['id']}/send")
    attempts, retries = [], []

    def fail(*args):
        attempts.append(True)
        raise smtplib.SMTPException("Synthetic failure")

    def retry(**kwargs):
        retries.append(kwargs)
        return Retry()

    monkeypatch.setattr(email, "deliver", fail)
    monkeypatch.setattr(email.send_email_message, "retry", retry)
    with pytest.raises(Retry):
        email.send_email_message.run(*published[0])
    assert len(attempts) == len(retries) == 1
    email.send_email_message.run(*published[0])
    assert len(attempts) == len(retries) == 1


@pytest.mark.parametrize("invalid", ["deleted", "merged", "expired", "inactive_actor", "revoked"])
def test_worker_rechecks_eligibility_and_rights_before_smtp(
    client, account, records, db_session, monkeypatch, email_outbox, invalid
):
    sign_in(client)
    monkeypatch.setattr(email.send_email_message, "apply_async", lambda **kwargs: None)
    message = draft(client, records).json()
    post(client, f"{BASE}/{message['id']}/send")
    row = db_session.get_one(EmailMessage, UUID(message["id"]))
    if invalid == "deleted":
        records.application.deleted_at = datetime.now(UTC)
    elif invalid == "merged":
        records.candidate.deleted_at = datetime.now(UTC)
    elif invalid == "expired":
        records.candidate.retention_until = datetime(2000, 1, 1).date()
    elif invalid == "inactive_actor":
        account.is_active = False
    else:
        account.role = UserRole.recruiter
        records.job.owner_id = records.other.id
    db_session.commit()
    deliver(row)
    assert not email_outbox and row.status == EmailStatus.failed and row.scheduled_for is None


def test_stale_retry_cannot_deliver_new_confirmation(
    client, account, records, db_session, monkeypatch, email_outbox
):
    sign_in(client)
    monkeypatch.setattr(email.send_email_message, "apply_async", lambda **kwargs: None)
    message = draft(client, records).json()
    post(client, f"{BASE}/{message['id']}/send")
    row = db_session.get_one(EmailMessage, UUID(message["id"]))
    old = row.message_id
    row.status = EmailStatus.failed
    db_session.commit()
    post(client, f"{BASE}/{message['id']}/send")
    assert old != row.message_id
    deliver(row, delivery_id=old)
    assert not email_outbox
    deliver(row)
    assert len(email_outbox) == 1
