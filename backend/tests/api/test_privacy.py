"""Only synthetic people and disposable storage; PostgreSQL queries are real."""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text

from app.core.errors import AppError
from app.models import (
    Activity,
    AiFeedback,
    AuditLog,
    Candidate,
    DataRequest,
    EmailMessage,
    InboundEmail,
    Interview,
    Offer,
    StageEvent,
    Task,
)
from app.models.enums import EmailStatus, ProcessingStatus
from app.models.users import UserRole
from app.schemas.privacy import ConsentInput, DataRequestInput
from app.services import privacy
from app.storage import LocalStorage, StorageError
from app.workers.tasks import process_cv_file, score_application
from tests.api import test_reports as report_tests
from tests.api.test_reports import add, report
from tests.auth_helpers import csrf_headers, sign_in

# Reuse the independent hand-computed fixture without calling a fixture directly.
dataset = report_tests.dataset

NOW = datetime(2026, 11, 10, tzinfo=UTC)
FAKE = "Dữ liệu giả T29"


@pytest.fixture
def records(db_session, dataset, tmp_path):
    session = db_session
    storage = LocalStorage(tmp_path / "cv")
    candidate = session.get_one(Candidate, dataset.apps[0].candidate_id)
    candidate.full_name = FAKE
    candidate.email = "t29-synthetic@example.invalid"
    candidate.phone = "+84000000029"
    candidate.location = FAKE
    candidate.current_title = FAKE
    candidate.years_experience = 3
    candidate.skills = [FAKE]
    candidate.languages = [FAKE]
    candidate.education = [{"school": FAKE}]
    candidate.experiences = [{"company": FAKE}]
    candidate.anonymized_text = FAKE
    candidate.embedding = [0.1] * 1024
    candidate.consent_at = NOW - timedelta(days=10)
    candidate.consent_note = FAKE
    candidate.retention_until = date(2027, 11, 10)
    for file in dataset.files:
        file.candidate_id = candidate.id
        file.storage_key = storage.put(b"synthetic CV only", "application/pdf")
        file.original_filename = FAKE
        file.extracted_text = FAKE
        file.parsed_json = {"full_name": FAKE}
    app = dataset.apps[0]
    app.rejected_reason = FAKE
    app.ai_criteria = [{"evidence": FAKE}]
    app.ai_reasons = [FAKE]
    app.ai_flags = [FAKE]
    for model, field in [
        (StageEvent, "note"),
        (AiFeedback, "comment"),
        (Interview, "feedback"),
        (Offer, "notes"),
    ]:
        for row in session.scalars(select(model).where(model.application_id == app.id)):
            setattr(row, field, FAKE)
    task = add(
        session,
        Task,
        title=FAKE,
        description=FAKE,
        application_id=app.id,
        job_id=app.job_id,
        assignee_id=dataset.a.id,
        created_by=dataset.a.id,
    )
    activity = session.scalars(select(Activity).where(Activity.type == "note")).one()
    activity.candidate_id = candidate.id
    activity.application_id = app.id
    activity.payload = {"text": FAKE}
    for linked, message_id in [(app.id, uuid4()), (None, dataset.files[0].id)]:
        add(
            session,
            EmailMessage,
            id=message_id,
            application_id=linked,
            to_email=candidate.email,
            cc=[candidate.email],
            subject=FAKE,
            body_html=FAKE,
            created_by=dataset.a.id,
            status=EmailStatus.queued,
            message_id=f"<{uuid4()}@example.invalid>",
            scheduled_for=NOW,
        )
    add(
        session,
        InboundEmail,
        from_email=candidate.email,
        subject=FAKE,
        message_id=f"<{uuid4()}@example.invalid>",
        received_at=NOW,
        processed_at=NOW,
        attachment_count=1,
        status="processed",
    )
    session.commit()
    return candidate, storage, task


def test_purge_erases_storage_and_sql_nulls_preserving_all_kpis(
    db_session, account, dataset, records, client
):
    candidate, storage, _ = records
    before = report(db_session, account).model_dump()
    keys = [f.storage_key for f in dataset.files]
    request = privacy.create_request(
        db_session, account, DataRequestInput(candidate_id=candidate.id, requested_by_note=FAKE)
    )
    result = privacy.execute_request(db_session, account, request.id, storage)
    assert result.status == "done" and result.handled_by == account.id
    assert result.requested_by_note is None
    assert all(not (storage.root / key).exists() for key in keys)
    assert report(db_session, account).model_dump() == before
    candidate_columns = [
        "full_name",
        "email",
        "phone",
        "location",
        "current_title",
        "years_experience",
        "skills",
        "languages",
        "education",
        "experiences",
        "consent_at",
        "consent_note",
        "anonymized_text",
        "embedding",
        "search_tsv",
    ]
    for column in candidate_columns:
        # Identifiers are fixed test constants, never user data.
        assert (
            db_session.scalar(
                text(f"SELECT {column} IS NULL FROM candidates WHERE id=:id"), {"id": candidate.id}
            )
            is True
        )
    for file in dataset.files:
        db_session.refresh(file)
        assert file.deleted_at is None  # CV-count fact remains in exactly the old population.
        assert (
            file.storage_key,
            file.original_filename,
            file.sha256,
            file.extracted_text,
            file.parsed_json,
        ) == (None,) * 5
    for model, field in [
        (StageEvent, "note"),
        (AiFeedback, "comment"),
        (Interview, "feedback"),
        (Offer, "notes"),
    ]:
        assert all(
            getattr(row, field) is None
            for row in db_session.scalars(
                select(model).where(model.application_id == dataset.apps[0].id)
            )
        )
    for row in db_session.scalars(select(EmailMessage)):
        assert (row.to_email, row.cc, row.subject, row.body_html, row.message_id) == (None,) * 5
        assert row.status == EmailStatus.cancelled and row.scheduled_for is None
    assert db_session.scalars(select(InboundEmail)).one().from_email is None
    audit = db_session.scalars(select(AuditLog).where(AuditLog.action == "candidate.purge")).one()
    assert audit.actor_id == account.id and audit.details == {}
    assert privacy.execute_request(db_session, account, request.id, storage).status == "done"
    assert (
        db_session.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.action == "candidate.purge")
        )
        == 1
    )
    sign_in(client)
    assert client.get(f"/api/v1/applications/{dataset.apps[0].id}").status_code == 404
    assert client.get(f"/api/v1/cv-files/{dataset.files[0].id}/download").status_code == 404


def test_storage_partial_failure_freezes_access_and_retry_finishes(
    db_session, account, dataset, records, client
):
    candidate, storage, _ = records
    request = privacy.create_request(
        db_session, account, DataRequestInput(candidate_id=candidate.id, requested_by_note=FAKE)
    )

    class FailingStorage:
        calls = 0

        def delete(self, key):
            self.calls += 1
            if self.calls == 2:
                raise StorageError("synthetic failure")
            storage.delete(key)

    with pytest.raises(AppError) as error:
        privacy.execute_request(db_session, account, request.id, FailingStorage())
    assert error.value.code == "STORAGE_UNAVAILABLE"
    db_session.refresh(candidate)
    assert candidate.deleted_at is not None and candidate.purge_pending_at is not None
    assert candidate.purged_at is None
    assert db_session.get_one(DataRequest, request.id).status == "open"
    assert (
        db_session.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.action == "candidate.purge")
        )
        == 0
    )
    sign_in(client)
    assert client.get(f"/api/v1/applications/{dataset.apps[0].id}").status_code == 404
    with pytest.raises(AppError):
        privacy.record_consent(
            db_session,
            account,
            candidate.id,
            ConsentInput(consent_at=NOW, note=FAKE, extend_retention=True),
            now=NOW,
        )
    assert privacy.execute_request(db_session, account, request.id, storage).status == "done"


@pytest.mark.parametrize(
    "days,expired,purged",
    [(0, False, False), (1, True, False), (29, True, False), (30, True, True), (90, True, True)],
)
def test_retention_boundary_and_system_actor(db_session, account, tmp_path, days, expired, purged):
    candidate = add(
        db_session,
        Candidate,
        full_name=FAKE,
        retention_until=date(2026, 11, 10) - timedelta(days=days),
    )
    privacy.enforce_retention(db_session, LocalStorage(tmp_path), now=NOW)
    db_session.refresh(candidate)
    assert (candidate.expired_at is not None) is expired
    assert (candidate.purged_at is not None) is purged
    privacy.enforce_retention(db_session, LocalStorage(tmp_path), now=NOW)
    audits = db_session.scalars(select(AuditLog).where(AuditLog.entity_id == candidate.id)).all()
    assert len(audits) == int(purged)
    assert all(a.actor_id is None for a in audits)


def test_retention_uses_vietnam_day_and_rechecks_extension(db_session, account, tmp_path):
    candidate = add(db_session, Candidate, full_name=FAKE, retention_until=date(2026, 11, 9))
    privacy.enforce_retention(
        db_session, LocalStorage(tmp_path), now=datetime(2026, 11, 9, 16, 59, tzinfo=UTC)
    )
    assert candidate.expired_at is None
    privacy.enforce_retention(
        db_session, LocalStorage(tmp_path), now=datetime(2026, 11, 9, 17, tzinfo=UTC)
    )
    assert candidate.expired_at is not None
    result = privacy.record_consent(
        db_session,
        account,
        candidate.id,
        ConsentInput(consent_at=NOW, note=FAKE, extend_retention=True),
        now=NOW,
    )
    assert result.retention_until == date(2027, 11, 10) and result.expired_at is None
    privacy.enforce_retention(db_session, LocalStorage(tmp_path), now=NOW + timedelta(days=30))
    assert candidate.purged_at is None


def test_consent_leap_day_replay_old_future_and_stale(db_session, account):
    candidate = add(db_session, Candidate, full_name=FAKE, retention_until=date(2028, 2, 29))
    now = datetime(2028, 2, 1, tzinfo=UTC)
    body = ConsentInput(consent_at=now, note=FAKE, extend_retention=True)
    assert privacy.record_consent(
        db_session, account, candidate.id, body, now=now
    ).retention_until == date(2029, 2, 28)
    for stamp, code in [
        (now, "CONSENT_NOT_NEW"),
        (now - timedelta(days=1), "CONSENT_NOT_NEW"),
        (now + timedelta(seconds=1), "INVALID_CONSENT"),
    ]:
        with pytest.raises(AppError) as error:
            privacy.record_consent(
                db_session,
                account,
                candidate.id,
                body.model_copy(update={"consent_at": stamp}),
                now=now,
            )
        assert error.value.code == code
    body = body.model_copy(update={"extend_retention": False})
    assert (
        privacy.record_consent(db_session, account, candidate.id, body, now=now).consent_at == now
    )
    other = add(db_session, Candidate, full_name=FAKE, retention_until=now.date())
    with pytest.raises(AppError) as error:
        privacy.record_consent(
            db_session,
            account,
            other.id,
            body.model_copy(
                update={"extend_retention": True, "consent_at": now - timedelta(days=31)}
            ),
            now=now,
        )
    assert error.value.code == "CONSENT_NOT_NEW"


@pytest.mark.parametrize("request_side", [0, 1])
def test_api_merge_conflict_preserves_deletion_confirmation(
    db_session, account, client, tmp_path, monkeypatch, request_side
):
    monkeypatch.setattr("app.api.privacy.build_storage", lambda settings: LocalStorage(tmp_path))
    candidates = [
        add(db_session, Candidate, full_name=f"Ứng viên giả {i}", retention_until=date(2099, 1, 1))
        for i in range(2)
    ]
    sign_in(client)
    headers = csrf_headers(client)
    selected = candidates[request_side]
    response = client.post(
        "/api/v1/data-requests",
        headers=headers,
        json={"candidate_id": str(selected.id), "requested_by_note": FAKE},
    )
    assert response.status_code == 201
    request_id = response.json()["id"]
    response = client.post(
        f"/api/v1/candidates/{candidates[0].id}/merge",
        headers=headers,
        json={"into_id": str(candidates[1].id)},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DATA_REQUEST_OPEN"
    confirmation = client.get("/api/v1/data-requests").json()["items"][0]
    assert confirmation["candidate_id"] == str(selected.id)
    assert confirmation["candidate_name"] == selected.full_name
    assert confirmation["status"] == "open"
    response = client.post(f"/api/v1/data-requests/{request_id}/execute", headers=headers)
    assert response.status_code == 200
    assert response.json()["candidate_id"] == str(selected.id)
    assert response.json()["status"] == "done"
    assert response.json()["candidate_name"] is None
    assert client.get("/api/v1/data-requests").json()["total"] == 1


def test_merged_aliases_are_erased_too(db_session, account, records):
    candidate, storage, _ = records
    alias = add(
        db_session,
        Candidate,
        full_name=FAKE,
        consent_note=FAKE,
        retention_until=candidate.retention_until,
        merged_into_id=candidate.id,
        deleted_at=NOW,
    )
    request = privacy.create_request(
        db_session, account, DataRequestInput(candidate_id=candidate.id, requested_by_note=FAKE)
    )
    privacy.execute_request(db_session, account, request.id, storage)
    db_session.refresh(alias)
    assert alias.full_name is None and alias.consent_note is None and alias.purged_at is not None
    assert (
        db_session.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.action == "candidate.purge")
        )
        == 2
    )


@pytest.mark.parametrize("role", [UserRole.lead, UserRole.recruiter])
def test_management_endpoints_are_admin_only(client, db_session, account, role):
    account.role = role
    db_session.commit()
    sign_in(client)
    for path in ["/settings/retention", "/data-requests", "/audit-log"]:
        assert client.get("/api/v1" + path).status_code == 403
    assert (
        client.post(
            "/api/v1/data-requests",
            json={"candidate_id": str(uuid4()), "requested_by_note": FAKE},
            headers=csrf_headers(client),
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/v1/data-requests/{uuid4()}/execute", headers=csrf_headers(client)
        ).status_code
        == 403
    )


def test_api_validation_scope_consent_request_and_filters(
    client, db_session, account, dataset, records, monkeypatch
):
    candidate, storage, _ = records
    monkeypatch.setattr("app.api.privacy.build_storage", lambda settings: storage)
    assert client.get("/api/v1/audit-log").status_code == 401
    sign_in(client)
    headers = csrf_headers(client)
    path = f"/api/v1/candidates/{candidate.id}/consent"
    stamp = datetime.now(UTC).isoformat()
    assert client.post(path, json={"consent_at": stamp, "note": FAKE}).status_code == 403
    for body in [
        {"consent_at": "2026-01-01", "note": FAKE},
        {"consent_at": stamp, "note": " "},
        {"consent_at": stamp, "note": FAKE, "role": "admin"},
    ]:
        assert client.post(path, json=body, headers=headers).status_code == 422
    response = client.post(path, json={"consent_at": stamp, "note": FAKE}, headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["retention_until"] == "2027-11-10"
    response = client.get(
        "/api/v1/settings/retention", params={"state": "all", "q": FAKE, "page_size": 1}
    )
    assert response.status_code == 200 and response.json()["total"] == 1
    assert len(response.json()["items"]) == 1
    body = {"candidate_id": str(candidate.id), "requested_by_note": FAKE}
    response = client.post("/api/v1/data-requests", json=body, headers=headers)
    assert response.status_code == 201
    request_id = response.json()["id"]
    assert (
        client.post("/api/v1/data-requests", json=body, headers=headers).json()["id"] == request_id
    )
    assert (
        client.post(f"/api/v1/data-requests/{request_id}/execute", headers=headers).json()["status"]
        == "done"
    )
    assert client.get("/api/v1/data-requests").json()["total"] == 1
    audits = client.get(
        "/api/v1/audit-log", params={"action": "candidate.purge", "actor_id": str(account.id)}
    ).json()
    assert audits["total"] == 1
    assert FAKE not in str(audits)
    assert client.get("/api/v1/audit-log", params={"system": True}).json()["total"] == 0
    for path in [
        "/settings/retention?page=0",
        "/settings/retention?state=bad",
        "/audit-log?actor_id=bad",
        "/data-requests?extra=true",
    ]:
        assert client.get("/api/v1" + path).status_code == 422


def test_recruiter_consent_needs_current_job_scope(client, db_session, account, dataset, records):
    candidate, _, _ = records
    sign_in(client, dataset.b.email)
    body = {"consent_at": datetime.now(UTC).isoformat(), "note": FAKE}
    path = f"/api/v1/candidates/{candidate.id}/consent"
    assert client.post(path, json=body, headers=csrf_headers(client)).status_code == 403
    sign_in(client, dataset.a.email)
    assert (
        client.post(
            path, json=body | {"extend_retention": True}, headers=csrf_headers(client)
        ).status_code
        == 403
    )
    assert client.post(path, json=body, headers=csrf_headers(client)).status_code == 200


def test_queued_score_cannot_repopulate_erased_data(
    db_session, account, records, dataset, monkeypatch
):
    from contextlib import contextmanager

    candidate, storage, _ = records
    request = privacy.create_request(
        db_session, account, DataRequestInput(candidate_id=candidate.id, requested_by_note=FAKE)
    )
    privacy.execute_request(db_session, account, request.id, storage)
    app = dataset.apps[0]
    app.ai_status = ProcessingStatus.pending
    db_session.commit()

    @contextmanager
    def session_scope():
        yield db_session

    monkeypatch.setattr("app.workers.tasks.worker_session", session_scope)
    score_application(str(app.id))
    db_session.refresh(app)
    assert app.ai_criteria is None and app.ai_reasons is None


def test_queued_parse_cannot_repopulate_erased_data(
    db_session, account, records, dataset, monkeypatch
):
    from contextlib import contextmanager

    candidate, storage, _ = records
    file = dataset.files[0]
    file.status = ProcessingStatus.pending
    db_session.commit()
    request = privacy.create_request(
        db_session, account, DataRequestInput(candidate_id=candidate.id, requested_by_note=FAKE)
    )
    privacy.execute_request(db_session, account, request.id, storage)

    @contextmanager
    def session_scope():
        yield db_session

    monkeypatch.setattr("app.workers.tasks.worker_session", session_scope)
    process_cv_file(str(file.id))
    db_session.refresh(file)
    assert file.error is None and file.extracted_text is None and file.parsed_json is None
    assert db_session.get_one(Candidate, candidate.id).full_name is None


@pytest.mark.parametrize("linked_activity", [False, True])
def test_forwarded_inbox_headers_erased_and_poll_replay_does_not_restore_cv(
    db_session, account, monkeypatch, tmp_path, linked_activity
):
    from app.core.config import get_settings
    from app.email import inbound
    from app.models import CvFile
    from tests.api.test_cv_pipeline import cv_docx
    from tests.api.test_inbound_email import mail

    storage = LocalStorage(tmp_path)
    monkeypatch.setattr(inbound, "build_storage", lambda settings: storage)
    raw = mail(attachments=[("synthetic.docx", cv_docx(FAKE))])
    inbound.ingest_message(db_session, raw, get_settings())
    file = db_session.scalars(select(CvFile)).one()
    candidate = add(
        db_session,
        Candidate,
        full_name=FAKE,
        email="different-t29@example.invalid",
        retention_until=date(2099, 1, 1),
    )
    file.candidate_id = candidate.id
    activity = db_session.scalars(select(Activity)).one()
    if linked_activity:
        activity.candidate_id = candidate.id
    db_session.commit()
    request = privacy.create_request(
        db_session, account, DataRequestInput(candidate_id=candidate.id, requested_by_note=FAKE)
    )
    privacy.execute_request(db_session, account, request.id, storage)
    inbox = db_session.scalars(select(InboundEmail)).one()
    assert inbox.from_email is None and inbox.subject is None
    assert inbox.message_id.startswith("purged:") and "@" not in inbox.message_id
    db_session.refresh(activity)
    assert activity.payload == {}
    inbound.ingest_message(db_session, raw, get_settings())
    assert db_session.scalar(select(func.count()).select_from(CvFile)) == 1
    assert list(tmp_path.iterdir()) == []


def test_daily_job_recovers_pending_manual_request(db_session, account, records):
    candidate, storage, _ = records
    request = privacy.create_request(
        db_session, account, DataRequestInput(candidate_id=candidate.id, requested_by_note=FAKE)
    )
    privacy.freeze_candidate(db_session, candidate.id, NOW)
    privacy.enforce_retention(db_session, storage, now=NOW)
    row = db_session.get_one(DataRequest, request.id, populate_existing=True)
    assert row.status == "done" and row.handled_by is None and row.handled_at == NOW


def test_retention_beat_is_due_at_two_am_vietnam_time():
    from app.core.config import Settings
    from app.workers.celery_app import celery_app, create_celery_app

    application = create_celery_app(Settings(_env_file=None, app_env="test"))
    try:
        entry = application.conf.beat_schedule["retention"]
        assert entry["task"] == "enforce_retention"
        assert "app.workers.retention" in application.conf.include
        assert application.amqp.router.route({}, "enforce_retention")["queue"].name == "default"
        schedule = entry["schedule"]
        schedule.app = application
        instant = datetime(2026, 11, 9, 19, tzinfo=UTC)
        schedule.nowfun = lambda: instant - timedelta(seconds=1)
        assert not schedule.is_due(instant - timedelta(days=1)).is_due
        schedule.nowfun = lambda: instant
        assert schedule.is_due(instant - timedelta(days=1)).is_due
    finally:
        application.close()
        celery_app.set_current()
