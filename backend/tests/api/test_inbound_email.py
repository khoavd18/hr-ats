"""T24: synthetic MIME mail, mocked imaplib, real PostgreSQL/storage/parse and memory SMTP."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from email.message import EmailMessage as MIMEMessage
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest
from alembic import command
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.redis import get_redis
from app.email import inbound
from app.models import Candidate, CvFile, EmailMessage, EmailTemplate, InboundEmail, Job
from app.models.enums import CandidateSource, EmailStatus, JobStatus, ProcessingStatus
from app.models.users import UserRole
from app.workers import email, tasks
from app.workers.celery_app import celery_app, create_celery_app
from tests.api.test_cv_pipeline import cv_docx
from tests.api.test_pipeline import seed_records
from tests.auth_helpers import sign_in
from tests.conftest import migration_config


def mail(subject="Hồ sơ giả T24", attachments=(), message_id="<synthetic-t24@example.invalid>"):
    message = MIMEMessage()
    message["From"] = "Nguồn giả <sender-t24@example.invalid>"
    message["Subject"] = subject
    if message_id:
        message["Message-ID"] = message_id
    message.set_content("Nội dung mail giả không được lưu hoặc ghi log.")
    for name, data in attachments:
        message.add_attachment(data, maintype="application", subtype="octet-stream", filename=name)
    return message.as_bytes()


@pytest.fixture
def runtime(db_session, account, monkeypatch, tmp_path):
    records = seed_records(db_session, account)
    records.job.status = JobStatus.open
    db_session.commit()
    settings = get_settings().model_copy(
        update={
            "imap_enabled": True,
            "imap_host": "imap.example.invalid",
            "imap_user": "synthetic",
            "imap_password": get_settings().smtp_password.__class__("synthetic-imap-password"),
            "storage_local_dir": tmp_path / "intake",
        }
    )

    @contextmanager
    def session():
        yield db_session

    for module in (inbound, tasks, email):
        monkeypatch.setattr(module, "worker_session", session)
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    status = {}
    monkeypatch.setattr(inbound, "_status", lambda config, error: status.update(error=error))
    box = Mock()
    box.__enter__ = Mock(return_value=box)
    box.__exit__ = Mock(return_value=False)
    box.login.return_value = "OK", []
    box.select.return_value = "OK", []
    messages = []

    def uid(command, *args):
        if command == "search":
            return "OK", [b" ".join(str(index + 1).encode() for index in range(len(messages)))]
        if command == "fetch":
            raw = messages[int(args[0]) - 1]
            if args[1] == "(RFC822.SIZE)":
                return "OK", [f"1 (RFC822.SIZE {len(raw)})".encode()]
            assert args[1] == "(BODY.PEEK[])"
            return "OK", [(b"1 (BODY[])", raw), b")"]
        assert command == "store" and args[1:] == ("+FLAGS", "(\\Seen)")
        return "OK", []

    box.uid.side_effect = uid
    factory = Mock(return_value=box)
    monkeypatch.setattr(inbound.imaplib, "IMAP4_SSL", factory)
    return SimpleNamespace(
        records=records,
        settings=settings,
        box=box,
        factory=factory,
        messages=messages,
        status=status,
    )


def count(session, model):
    return session.scalar(select(func.count()).select_from(model))


def test_two_attachments_replay_and_no_attachments_are_recorded(
    runtime, db_session, email_outbox, caplog
):
    runtime.messages.extend(
        [
            mail(
                f"Ứng tuyển {inbound.job_code(runtime.records.job.id)}",
                [
                    (
                        "../cv-gia-1.docx",
                        cv_docx(
                            "Ứng viên giả T24 A\nEmail: cv-t24-a@example.invalid\nKỹ năng: Python"
                        ),
                    ),
                    (
                        "cv-gia-2.docx",
                        cv_docx(
                            "Ứng viên giả T24 B\nEmail: cv-t24-b@example.invalid\nKỹ năng: SQL"
                        ),
                    ),
                ],
            ),
            mail(attachments=(), message_id="<synthetic-empty@example.invalid>"),
        ]
    )
    inbound.poll_inbox.run()
    files = db_session.scalars(select(CvFile).order_by(CvFile.original_filename)).all()
    assert len(files) == 2
    assert all(file.status == ProcessingStatus.done for file in files)
    assert all(file.source == CandidateSource.email and file.uploaded_by is None for file in files)
    assert all(file.job_id == runtime.records.job.id for file in files)
    assert files[0].original_filename == "cv-gia-1.docx"
    candidates = [db_session.get_one(Candidate, file.candidate_id) for file in files]
    assert all(
        candidate.source == CandidateSource.email and candidate.consent_at is None
        for candidate in candidates
    )
    assert len(email_outbox) == 2
    assert {str(message["To"]) for message in email_outbox} == {
        "cv-t24-a@example.invalid",
        "cv-t24-b@example.invalid",
    }
    assert all(
        "không thay thế" in message.get_body(preferencelist=("plain",)).get_content()
        for message in email_outbox
    )
    records = db_session.scalars(select(InboundEmail).order_by(InboundEmail.attachment_count)).all()
    assert [(row.status, row.attachment_count) for row in records] == [
        ("ignored", 0),
        ("processed", 2),
    ]
    assert all(row.processed_at is not None for row in records)
    assert not hasattr(records[1], "body")
    inbound.poll_inbox.run()
    assert count(db_session, CvFile) == 2 and count(db_session, InboundEmail) == 2
    assert len(email_outbox) == 2 and count(db_session, EmailMessage) == 2
    assert runtime.status["error"] == ""
    assert runtime.factory.call_args.kwargs["timeout"] == 15
    assert runtime.factory.call_args.kwargs["ssl_context"].check_hostname
    assert "sender-t24@example.invalid" not in caplog.text
    assert "cv-t24-a@example.invalid" not in caplog.text
    assert "Nội dung mail giả" not in caplog.text


@pytest.mark.parametrize(
    "mode", ["title", "no-job", "no-email", "inactive", "confirmation", "failed-parse"]
)
def test_receipt_only_after_success_and_only_for_active_automatic_template(
    runtime, db_session, email_outbox, mode
):
    template = db_session.scalar(select(EmailTemplate).where(EmailTemplate.key == "cv_received"))
    if mode == "inactive":
        template.is_active = False
    if mode == "confirmation":
        template.requires_confirmation = True
    db_session.commit()
    text = "Ứng viên giả T24\nKỹ năng: Python"
    if mode != "no-email":
        text += "\nEmail: cv-t24-receipt@example.invalid"
    data = b"%PDF-corrupt synthetic" if mode == "failed-parse" else cv_docx(text)
    runtime.messages.append(
        mail(
            runtime.records.job.title if mode == "title" else "Không gắn Job",
            [("cv.docx", data)],
        )
    )
    inbound.poll_inbox.run()
    file = db_session.scalar(select(CvFile))
    assert file is not None
    assert file.job_id == (runtime.records.job.id if mode == "title" else None)
    assert len(email_outbox) == (1 if mode in {"title", "no-job"} else 0)
    if mode == "failed-parse":
        assert file.status == ProcessingStatus.failed
    else:
        assert file.status == ProcessingStatus.done


def test_duplicate_hash_and_invalid_attachment_and_missing_message_id(runtime, db_session):
    data = cv_docx("Ứng viên giả T24\nKỹ năng: Python")
    raw = mail(
        attachments=[("a.docx", data), ("b.docx", data), ("x.pdf", b"MZ-invalid")], message_id=None
    )
    runtime.messages.append(raw)
    inbound.poll_inbox.run()
    inbound.poll_inbox.run()
    assert count(db_session, CvFile) == 1
    record = db_session.scalar(select(InboundEmail))
    assert record.attachment_count == 3 and record.error and record.status == "processed"
    assert record.message_id.startswith("sha256:")


def test_storage_failure_rolls_back_marker_and_files_then_retry_succeeds(
    runtime, db_session, monkeypatch
):
    runtime.messages.append(mail(attachments=[("cv.docx", cv_docx("Kỹ năng: Python"))]))
    original = inbound.build_storage
    storage = Mock()
    storage.put.side_effect = OSError("synthetic private failure")
    monkeypatch.setattr(inbound, "build_storage", lambda config: storage)
    inbound.poll_inbox.run()
    assert count(db_session, InboundEmail) == 0 and count(db_session, CvFile) == 0
    assert runtime.status["error"] == "IMAP_READ_FAILED"
    assert not any(call.args[0] == "store" for call in runtime.box.uid.call_args_list)
    monkeypatch.setattr(inbound, "build_storage", original)
    inbound.poll_inbox.run()
    assert count(db_session, InboundEmail) == 1 and count(db_session, CvFile) == 1


def test_commit_publish_gap_is_recovered_on_next_poll(
    runtime, db_session, monkeypatch, email_outbox
):
    runtime.messages.append(
        mail(
            attachments=[
                ("cv.docx", cv_docx("Email: recover-t24@example.invalid\nKỹ năng: Python"))
            ]
        )
    )
    publish = monkeypatch.context()
    with publish as patch:
        patch.setattr(
            inbound.process_cv_file, "delay", Mock(side_effect=RuntimeError("queue down"))
        )
        inbound.poll_inbox.run()
    assert db_session.scalar(select(CvFile)).status == ProcessingStatus.pending
    assert not email_outbox
    runtime.messages.clear()
    inbound.poll_inbox.run()
    assert db_session.scalar(select(CvFile)).status == ProcessingStatus.done
    assert len(email_outbox) == 1


@pytest.mark.parametrize("change", ["disabled", "deleted", "changed-email", "offer", "upload"])
def test_receipt_worker_rechecks_eligibility_and_cannot_send_other_templates(
    runtime, db_session, monkeypatch, email_outbox, change
):
    runtime.messages.append(
        mail(
            attachments=[
                ("cv.docx", cv_docx("Email: recheck-t24@example.invalid\nKỹ năng: Python"))
            ]
        )
    )
    with monkeypatch.context() as patch:
        patch.setattr(
            email.send_email_message, "apply_async", Mock(side_effect=RuntimeError("queue down"))
        )
        inbound.poll_inbox.run()
    row = db_session.scalar(select(EmailMessage))
    assert row.status == EmailStatus.queued and not email_outbox
    cv_file = db_session.get_one(CvFile, row.id)
    candidate = db_session.get_one(Candidate, cv_file.candidate_id)
    if change == "disabled":
        runtime.settings.imap_enabled = False
    elif change == "deleted":
        candidate.deleted_at = row.created_at
    elif change == "changed-email":
        candidate.email = "different-t24@example.invalid"
    elif change == "offer":
        row.template_id = db_session.scalar(
            select(EmailTemplate.id).where(EmailTemplate.key == "offer")
        )
    else:
        cv_file.source = CandidateSource.upload
    db_session.commit()
    email.send_email_message.run(str(row.id), row.message_id, row.scheduled_for.isoformat())
    assert row.status == EmailStatus.failed and not email_outbox


def test_imap_errors_are_safe_and_disabled_never_connects(runtime):
    runtime.factory.side_effect = RuntimeError("synthetic-imap-password sender-t24@example.invalid")
    inbound.poll_inbox.run()
    assert runtime.status["error"] == "IMAP_READ_FAILED"
    runtime.settings.imap_enabled = False
    runtime.factory.reset_mock()
    inbound.poll_inbox.run()
    runtime.factory.assert_not_called()


def test_oversized_message_is_not_downloaded_and_configuration_failure_is_visible(runtime):
    runtime.messages.append(b"synthetic oversized envelope")
    original = runtime.box.uid.side_effect

    def uid(operation, *args):
        if operation == "fetch":
            assert args[1] == "(RFC822.SIZE)"
            return "OK", [f"1 (RFC822.SIZE {inbound.MAX_MESSAGE_BYTES + 1})".encode()]
        return original(operation, *args)

    runtime.box.uid.side_effect = uid
    inbound.poll_inbox.run()
    assert runtime.status["error"] == "IMAP_MESSAGE_TOO_LARGE"
    runtime.settings.imap_host = ""
    runtime.factory.reset_mock()
    inbound.poll_inbox.run()
    assert runtime.status["error"] == "IMAP_NOT_CONFIGURED"
    runtime.factory.assert_not_called()


def test_concurrent_intake_and_commit_before_dispatch(empty_engine, tmp_path, monkeypatch):
    with empty_engine.begin() as connection:
        config = migration_config()
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    settings = get_settings().model_copy(
        update={"imap_enabled": True, "storage_local_dir": tmp_path}
    )
    raw = mail(
        attachments=[("a.docx", cv_docx("Kỹ năng: Python")), ("b.docx", cv_docx("Kỹ năng: SQL"))]
    )
    barrier = Barrier(2)

    def ingest():
        with Session(empty_engine) as session:
            barrier.wait(timeout=10)
            inbound.ingest_message(session, raw, settings)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(ingest) for _ in range(2)]
        for future in futures:
            future.result(timeout=30)
    published = []

    def dispatch(file_id):
        with Session(empty_engine) as observer:
            file = observer.get_one(CvFile, UUID(file_id))
            assert file.status == ProcessingStatus.pending
            published.append(file.id)

    monkeypatch.setattr(inbound.process_cv_file, "delay", dispatch)
    with Session(empty_engine) as session:
        assert count(session, InboundEmail) == 1 and count(session, CvFile) == 2
        inbound.recover_intake(session, settings)
        assert set(published) == set(session.scalars(select(CvFile.id)))


def test_job_matching_rejects_closed_unknown_and_ambiguous(runtime, db_session):
    job = runtime.records.job
    assert inbound.match_job(db_session, f"Ứng tuyển {inbound.job_code(job.id)}") == job
    assert inbound.match_job(db_session, "  " + job.title.upper() + "  ") == job
    assert inbound.match_job(db_session, "[JOB-00000000] " + job.title) is None
    other = Job(
        title=job.title,
        description="Giả",
        owner_id=job.owner_id,
        hiring_unit_id=job.hiring_unit_id,
        status=JobStatus.open,
    )
    db_session.add(other)
    db_session.flush()
    assert inbound.match_job(db_session, job.title) is None
    assert (
        inbound.match_job(db_session, inbound.job_code(job.id) + inbound.job_code(other.id)) is None
    )
    job.status = JobStatus.closed
    db_session.flush()
    assert inbound.match_job(db_session, inbound.job_code(job.id)) is None


def test_beat_only_registers_enabled_poll():
    for enabled in (False, True):
        application = create_celery_app(get_settings().model_copy(update={"imap_enabled": enabled}))
        try:
            assert bool(application.conf.beat_schedule) == enabled
            if enabled:
                assert application.conf.beat_schedule["poll-inbox"] == {
                    "task": "poll_inbox",
                    "schedule": 300.0,
                }
                assert application.conf.task_routes["poll_inbox"] == {"queue": "email"}
        finally:
            application.close()
            celery_app.set_current()


@pytest.mark.parametrize(
    "role,status", [(UserRole.admin, 200), (UserRole.lead, 200), (UserRole.recruiter, 403)]
)
def test_mailbox_status_permissions_and_no_credentials(
    client, app, account, db_session, role, status
):
    account.role = role
    db_session.commit()
    sign_in(client)
    redis_client = Mock()
    redis_client.hgetall.return_value = {
        "last_read_at": "2026-11-09T01:00:00+00:00",
        "last_error": "IMAP_READ_FAILED",
        "password": "must-not-return",
    }
    app.dependency_overrides[get_redis] = lambda: redis_client
    result = client.get("/api/v1/settings/mailbox")
    assert result.status_code == status
    if status == 200:
        assert set(result.json()) == {"enabled", "last_read_at", "last_error"}
        assert result.json()["last_error"] == "IMAP_READ_FAILED"
        assert "must-not-return" not in result.text


def test_mailbox_status_auth_and_safe_redis_failure(client, app, account):
    assert client.get("/api/v1/settings/mailbox").status_code == 401
    sign_in(client)
    redis_client = Mock()
    redis_client.hgetall.side_effect = RuntimeError("private failure")
    app.dependency_overrides[get_redis] = lambda: redis_client
    assert client.get("/api/v1/settings/mailbox").json()["last_error"] == "IMAP_STATUS_UNAVAILABLE"
