"""T19: exhaustive transitions, human undo, scope and atomic history on PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from itertools import product
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Activity, Application, Candidate, HiringUnit, Job, JobMember, User
from app.models.applications import StageEvent
from app.models.enums import ActivityType, ApplicationStage, HiringUnitKind
from app.models.users import UserRole
from app.schemas.pipeline import RejectedReason
from app.services import pipeline
from app.services.activity import log_activity
from tests.auth_helpers import csrf_headers, sign_in
from tests.conftest import migration_config

# Written from spec 02, independently of the implementation's transition helper.
ALLOWED = {
    "new": {"screening", "rejected", "withdrawn"},
    "screening": {"new", "submitted", "rejected", "withdrawn"},
    "submitted": {"screening", "interview", "rejected", "withdrawn"},
    "interview": {"submitted", "offer", "rejected", "withdrawn"},
    "offer": {"interview", "hired", "rejected", "withdrawn"},
    "hired": set(),
    "rejected": set(),
    "withdrawn": set(),
}


def seed_records(session, actor):
    candidate = Candidate(full_name="Ứng viên giả T19", retention_until=date(2099, 1, 1))
    unit = HiringUnit(name="Đơn vị giả T19", kind=HiringUnitKind.department)
    other = User(
        email="pipeline@example.invalid",
        full_name="Recruiter giả T19",
        password_hash=actor.password_hash,
        role=UserRole.recruiter,
    )
    session.add_all([candidate, unit, other])
    session.flush()
    job = Job(
        title="Job giả T19", description="Mô tả giả", owner_id=actor.id, hiring_unit_id=unit.id
    )
    session.add(job)
    session.flush()
    application = Application(candidate_id=candidate.id, job_id=job.id, owner_id=other.id)
    session.add(application)
    session.commit()
    return SimpleNamespace(candidate=candidate, job=job, application=application, other=other)


@pytest.fixture
def records(db_session, account):
    return seed_records(db_session, account)


def post(client, records, action="move", body=None):
    return client.post(
        f"/api/v1/applications/{records.application.id}/{action}",
        json=body,
        headers=csrf_headers(client),
    )


def count(session, model):
    return session.scalar(select(func.count()).select_from(model))


@pytest.mark.parametrize("before,after", list(product(ApplicationStage, repeat=2)))
def test_all_64_stage_pairs_and_undo_valid_changes(
    client, account, records, db_session, before, after, email_outbox
):
    records.application.stage = before
    entered = datetime.now(UTC) - timedelta(days=2)
    records.application.stage_entered_at = entered
    db_session.commit()
    sign_in(client)
    body = {"to_stage": after, "note": "  Ghi chú giả T19  "}
    if after == ApplicationStage.rejected:
        body["rejected_reason"] = "thiếu kỹ năng"
    response = post(client, records, body=body)
    valid = after in ALLOWED[before]
    assert response.status_code == (200 if valid else 409), response.text
    db_session.refresh(records.application)
    assert records.application.stage == (after if valid else before)
    assert count(db_session, StageEvent) == count(db_session, Activity) == int(valid)
    assert email_outbox == []
    if not valid:
        assert response.json()["error"]["code"] == "INVALID_STAGE_TRANSITION"
        assert records.application.stage_entered_at == entered
        return
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    assert data["suggested_email"] is None
    assert data["application"]["stage"] == after
    assert records.application.stage_entered_at > entered
    assert records.application.owner_id == records.other.id
    event = db_session.scalars(select(StageEvent)).one()
    assert (event.from_stage, event.to_stage, event.actor_id) == (before, after, account.id)
    assert event.note == "Ghi chú giả T19"
    assert event.occurred_at == records.application.stage_entered_at
    assert records.application.rejected_reason == body.get("rejected_reason")
    original_event_id = event.id
    undone = post(client, records, "undo")
    assert undone.status_code == 200, undone.text
    assert undone.json()["stage"] == before
    assert undone.json()["rejected_reason"] is None
    assert undone.headers["cache-control"] == "no-store"
    events = list(db_session.scalars(select(StageEvent).order_by(StageEvent.occurred_at)))
    assert len(events) == count(db_session, Activity) == 2
    assert events[0].id == original_event_id and events[0].deleted_at is None
    assert (events[1].from_stage, events[1].to_stage) == (after, before)
    assert events[1].actor_id == account.id
    activities = list(db_session.scalars(select(Activity).order_by(Activity.occurred_at)))
    assert activities[1].payload["undo_of"] == str(original_event_id)
    assert all(a.type == ActivityType.stage_changed for a in activities)
    assert all(a.candidate_id == records.candidate.id for a in activities)
    assert all("note" not in a.payload and "rejected_reason" not in a.payload for a in activities)
    assert email_outbox == []


@pytest.mark.parametrize("reason", list(RejectedReason))
def test_all_six_standard_rejection_reasons(client, account, records, reason):
    sign_in(client)
    response = post(client, records, body={"to_stage": "rejected", "rejected_reason": reason})
    assert response.status_code == 200
    assert response.json()["application"]["rejected_reason"] == reason


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"to_stage": None},
        {"to_stage": "unknown-private-input"},
        {"to_stage": "rejected"},
        {"to_stage": "rejected", "rejected_reason": ""},
        {"to_stage": "rejected", "rejected_reason": "unknown-private-input"},
        {"to_stage": "screening", "rejected_reason": "khác"},
        {"to_stage": "screening", "note": "   "},
        {"to_stage": "screening", "note": "x" * 10001},
        {"to_stage": "screening", "actor_id": "unknown-private-input"},
        {"to_stage": "screening", "suggested_email": {}},
    ],
)
def test_validation_is_safe_and_writes_nothing(client, account, records, db_session, body):
    sign_in(client)
    response = post(client, records, body=body)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "unknown-private-input" not in response.text
    assert count(db_session, StageEvent) == count(db_session, Activity) == 0


def clock_at(monkeypatch, value):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            assert tz == UTC
            return value

    monkeypatch.setattr(pipeline, "datetime", Clock)


@pytest.mark.parametrize(
    "elapsed,status",
    [
        (timedelta(hours=24) - timedelta(microseconds=1), 200),
        (timedelta(hours=24), 200),
        (timedelta(hours=24) + timedelta(microseconds=1), 409),
        (timedelta(seconds=-1), 409),
    ],
)
def test_undo_24_hour_boundary(client, account, records, db_session, monkeypatch, elapsed, status):
    start = datetime.now(UTC)
    clock_at(monkeypatch, start)
    sign_in(client)
    assert post(client, records, body={"to_stage": "screening"}).status_code == 200
    clock_at(monkeypatch, start + elapsed)
    response = post(client, records, "undo")
    assert response.status_code == status, response.text
    assert count(db_session, StageEvent) == (2 if status == 200 else 1)
    if status == 409:
        assert response.json()["error"]["code"] == "UNDO_EXPIRED"


@pytest.mark.parametrize(
    "role,status", [(UserRole.recruiter, 403), (UserRole.lead, 200), (UserRole.admin, 200)]
)
def test_other_recruiter_cannot_undo_but_lead_and_admin_can(
    client, account, records, db_session, role, status
):
    account.role = UserRole.recruiter
    records.other.role = role
    db_session.add(JobMember(job_id=records.job.id, user_id=records.other.id))
    db_session.commit()
    sign_in(client)
    assert post(client, records, body={"to_stage": "screening"}).status_code == 200
    sign_in(client, records.other.email)
    response = post(client, records, "undo")
    assert response.status_code == status, response.text
    if status == 403:
        assert response.json()["error"]["code"] == "UNDO_FORBIDDEN"
        assert count(db_session, StageEvent) == 1
    else:
        latest = db_session.scalars(
            select(StageEvent).order_by(StageEvent.occurred_at.desc())
        ).first()
        assert latest.actor_id == records.other.id


def test_only_latest_move_can_be_undone_once(client, account, records, db_session):
    account.role = UserRole.recruiter
    db_session.add(JobMember(job_id=records.job.id, user_id=records.other.id))
    db_session.commit()
    sign_in(client)
    assert post(client, records, body={"to_stage": "screening"}).status_code == 200
    sign_in(client, records.other.email)
    assert post(client, records, body={"to_stage": "submitted"}).status_code == 200
    sign_in(client)
    assert post(client, records, "undo").json()["error"]["code"] == "UNDO_FORBIDDEN"
    sign_in(client, records.other.email)
    assert post(client, records, "undo").json()["stage"] == "screening"
    assert post(client, records, "undo").json()["error"]["code"] == "UNDO_NOT_AVAILABLE"
    assert count(db_session, StageEvent) == 3
    # A new explicit change enables its own single undo.
    assert post(client, records, body={"to_stage": "submitted"}).status_code == 200
    assert post(client, records, "undo").json()["stage"] == "screening"
    assert count(db_session, StageEvent) == 5


@pytest.mark.parametrize("history", ["none", "initial", "mismatch", "deleted"])
def test_undo_rejects_missing_or_inconsistent_history(
    client, account, records, db_session, history
):
    if history != "none":
        db_session.add(
            StageEvent(
                application_id=records.application.id,
                from_stage=None if history == "initial" else ApplicationStage.screening,
                to_stage=ApplicationStage.offer if history == "mismatch" else ApplicationStage.new,
                actor_id=account.id,
                deleted_at=datetime.now(UTC) if history == "deleted" else None,
            )
        )
        db_session.commit()
    sign_in(client)
    response = post(client, records, "undo")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "UNDO_NOT_AVAILABLE"
    assert count(db_session, Activity) == 0


@pytest.mark.parametrize("action", ["move", "undo"])
def test_activity_failure_rolls_back_stage_timestamp_reason_and_event(
    client, account, records, db_session, monkeypatch, action
):
    sign_in(client)
    if action == "undo":
        assert (
            post(
                client, records, body={"to_stage": "rejected", "rejected_reason": "khác"}
            ).status_code
            == 200
        )
    db_session.refresh(records.application)
    before = (
        records.application.stage,
        records.application.stage_entered_at,
        records.application.rejected_reason,
    )
    before_count = count(db_session, StageEvent)

    def fail(*args, **kwargs):
        raise RuntimeError("private-internal-detail")

    monkeypatch.setattr(pipeline, "log_activity", fail)
    response = post(
        client,
        records,
        action,
        {"to_stage": "rejected", "rejected_reason": "khác"} if action == "move" else None,
    )
    assert response.status_code == 500 and "private-internal-detail" not in response.text
    db_session.expire_all()
    after = db_session.get(Application, records.application.id)
    assert (after.stage, after.stage_entered_at, after.rejected_reason) == before
    assert count(db_session, StageEvent) == count(db_session, Activity) == before_count


@pytest.mark.parametrize("role", list(UserRole))
def test_pipeline_returns_all_eight_columns_in_order_and_safe_cards(
    client, account, records, db_session, role
):
    account.role = role
    entered = datetime.now(UTC) - timedelta(days=1)
    records.application.stage_entered_at = entered
    for stage in ApplicationStage:
        candidate = Candidate(full_name=f"Ứng viên giả {stage}", retention_until=date(2099, 1, 1))
        db_session.add(candidate)
        db_session.flush()
        db_session.add(
            Application(
                candidate_id=candidate.id, job_id=records.job.id, owner_id=account.id, stage=stage
            )
        )
    db_session.commit()
    sign_in(client)
    response = client.get(f"/api/v1/jobs/{records.job.id}/pipeline")
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    assert [c["stage"] for c in data["columns"]] == list(ApplicationStage)
    assert data["total"] == 9
    assert [c["total"] for c in data["columns"]] == [2, 1, 1, 1, 1, 1, 1, 1]
    assert data["columns"][0]["items"][0]["id"] == str(records.application.id)
    assert set(data["columns"][0]["items"][0]) == {
        "id",
        "candidate_id",
        "candidate_name",
        "stage",
        "stage_entered_at",
        "owner_id",
        "ai_status",
        "ai_level",
    }
    assert count(db_session, StageEvent) == count(db_session, Activity) == 0


@pytest.mark.parametrize("state", ["application_deleted", "candidate_deleted", "merged", "expired"])
def test_ineligible_records_hidden_and_cannot_move_or_undo(
    client, account, records, db_session, state
):
    if state == "application_deleted":
        records.application.deleted_at = datetime.now(UTC)
    elif state == "candidate_deleted":
        records.candidate.deleted_at = datetime.now(UTC)
    elif state == "merged":
        target = Candidate(full_name="Đích giả", retention_until=date(2099, 1, 1))
        db_session.add(target)
        db_session.flush()
        records.candidate.merged_into_id = target.id
    else:
        records.candidate.retention_until = date(2000, 1, 1)
    db_session.commit()
    sign_in(client)
    data = client.get(f"/api/v1/jobs/{records.job.id}/pipeline").json()
    assert data["total"] == 0 and all(c["items"] == [] for c in data["columns"])
    for action in ("move", "undo"):
        assert (
            post(
                client, records, action, {"to_stage": "screening"} if action == "move" else None
            ).status_code
            == 404
        )


def test_recruiter_job_scope_membership_revocation_and_application_owner_not_sufficient(
    client, account, records, db_session
):
    sign_in(client, records.other.email)
    url = f"/api/v1/jobs/{records.job.id}/pipeline"
    assert client.get(url).status_code == 403
    assert post(client, records, body={"to_stage": "screening"}).status_code == 403
    assert post(client, records, "undo").status_code == 403
    member = JobMember(job_id=records.job.id, user_id=records.other.id)
    db_session.add(member)
    db_session.commit()
    assert client.get(url).status_code == 200
    assert post(client, records, body={"to_stage": "screening"}).status_code == 200
    db_session.delete(member)
    db_session.commit()
    assert client.get(url).status_code == 403
    assert post(client, records, "undo").status_code == 403
    assert post(client, records, body={"to_stage": "submitted"}).status_code == 403
    records.application.deleted_at = datetime.now(UTC)
    db_session.commit()
    assert client.get(url).status_code == 403  # Also check scope for an empty pipeline.


def test_auth_csrf_origin_missing_ids_and_no_note_in_logs(client, account, records, caplog):
    url = f"/api/v1/jobs/{records.job.id}/pipeline"
    assert client.get(url).status_code == 401
    csrf_headers(client)
    assert post(client, records, body={"to_stage": "screening"}).status_code == 401
    assert post(client, records, "undo").status_code == 401
    sign_in(client)
    for action in ("move", "undo"):
        endpoint = f"/api/v1/applications/{records.application.id}/{action}"
        assert client.post(endpoint, json={"to_stage": "screening"}).status_code == 403
        assert (
            client.post(
                endpoint,
                json={"to_stage": "screening"},
                headers={**csrf_headers(client), "Origin": "https://example.invalid"},
            ).status_code
            == 403
        )
        assert (
            client.post(
                f"/api/v1/applications/{uuid4()}/{action}",
                json={"to_stage": "screening"} if action == "move" else None,
                headers=csrf_headers(client),
            ).status_code
            == 404
        )
    assert client.get(f"/api/v1/jobs/{uuid4()}/pipeline").status_code == 404
    assert client.get("/api/v1/jobs/not-a-uuid/pipeline").status_code == 422
    assert (
        post(
            client, records, body={"to_stage": "screening", "note": "private-synthetic-note-T19"}
        ).status_code
        == 200
    )
    assert "private-synthetic-note-T19" not in caplog.text


def test_direct_service_enforces_permissions_and_rejection_validation(account, records, db_session):
    with pytest.raises(AppError) as error:
        pipeline.move(db_session, account, records.application.id, ApplicationStage.rejected)
    assert error.value.status == 422
    with pytest.raises(AppError) as error:
        pipeline.move(db_session, records.other, records.application.id, ApplicationStage.screening)
    assert error.value.status == 403


@pytest.mark.parametrize("key", ["cv_file_id", "stage_event_id", "undo_of"])
def test_uuid_metadata_is_not_mistaken_for_phone(account, records, db_session, key):
    # Canonical v4 UUID from the reproduced core-data fixture failure; no personal data.
    reference = "c8287d02-8472-4722-8599-de8978b15aaf"
    activity = log_activity(
        db_session,
        type=ActivityType.stage_changed,
        actor_id=account.id,
        application_id=records.application.id,
        payload={key: reference},
    )
    db_session.flush()
    db_session.refresh(activity)
    assert activity.payload == {key: reference}


@pytest.mark.parametrize(
    "metadata",
    [
        {"stage_event_id": "0900000000"},
        {"undo_of": "synthetic@example.invalid"},
        {"email": "c8287d02-8472-4722-8599-de8978b15aaf"},
        {"stage_event_id": "c8287d02-8472-4722-8599-de8978b15aaf 0900000000"},
        {"stage_event_id": "c8287d02-8472-4722-8599-de8978b15aaf", "text": "private"},
    ],
)
def test_uuid_reference_handling_keeps_pii_and_sensitive_key_checks(db_session, metadata):
    with pytest.raises(ValueError, match="non-sensitive JSON metadata only"):
        log_activity(db_session, type=ActivityType.stage_changed, payload=metadata)


@pytest.mark.parametrize("action", ["move", "undo"])
def test_concurrent_duplicate_actions_apply_once_with_fresh_state(empty_engine, action):
    with empty_engine.begin() as connection:
        config = migration_config()
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    with Session(empty_engine) as session:
        actor = User(
            email="concurrent@example.invalid",
            full_name="HR giả",
            role=UserRole.admin,
            password_hash="unused-synthetic-hash",
        )
        session.add(actor)
        session.flush()
        records = seed_records(session, actor)
        actor_id, application_id = actor.id, records.application.id
        if action == "undo":
            pipeline.move(session, actor, application_id, ApplicationStage.screening)
    barrier = Barrier(2)

    def perform(_):
        with Session(empty_engine) as session:
            actor = session.get_one(User, actor_id)
            # Cache stale state in both sessions before either mutation starts.
            cached = session.get_one(Application, application_id)
            assert cached.stage == ("screening" if action == "undo" else "new")
            barrier.wait(timeout=10)
            try:
                if action == "move":
                    pipeline.move(session, actor, application_id, ApplicationStage.screening)
                else:
                    pipeline.undo(session, actor, application_id)
            except AppError as error:
                return error.code
            return "ok"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(perform, range(2)))
    assert sorted(results) == sorted(
        ["ok", "UNDO_NOT_AVAILABLE" if action == "undo" else "INVALID_STAGE_TRANSITION"]
    )
    with Session(empty_engine) as session:
        assert (
            count(session, StageEvent) == count(session, Activity) == (2 if action == "undo" else 1)
        )
        assert session.get_one(Application, application_id).stage == (
            "new" if action == "undo" else "screening"
        )
