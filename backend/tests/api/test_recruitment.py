"""T21 integration tests against PostgreSQL, using only synthetic records."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from alembic import command
from icalendar import Calendar
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Activity, Interview, JobMember, Offer, Placement, StageEvent
from app.models.enums import ApplicationStage
from app.models.users import UserRole
from app.schemas.recruitment import PlacementCreate
from app.services import recruitment
from tests.api.test_pipeline import seed_records
from tests.auth_helpers import csrf_headers, sign_in
from tests.conftest import migration_config

INTERVIEW = {
    "round": 1,
    "scheduled_at": "2026-11-10T09:30:00+07:00",
    "duration_minutes": 75,
    "location_or_link": "Phòng giả, A; tầng 2\\3\nEND:VEVENT\n" + "Địa điểm giả " * 20,
    "interviewers": ["Người phỏng vấn giả", "interviewer@example.invalid"],
}
PLACEMENT = {"start_date": "2026-12-01", "fee_amount": 1000000, "guarantee_until": "2027-02-01"}


@pytest.fixture
def records(db_session, account):
    data = seed_records(db_session, account)
    data.application.stage = ApplicationStage.submitted
    db_session.commit()
    return data


def create(client, records, action="interviews", body=None):
    return client.post(
        f"/api/v1/applications/{records.application.id}/{action}",
        json=INTERVIEW if body is None else body,
        headers=csrf_headers(client),
    )


def patch(client, path, body):
    return client.patch("/api/v1" + path, json=body, headers=csrf_headers(client))


def count(session, model):
    return session.scalar(select(func.count()).select_from(model))


def test_interviews_stage_history_results_and_ics_round_trip(
    client, account, records, db_session, email_outbox
):
    sign_in(client)
    first = create(client, records)
    assert first.status_code == 201, first.text
    row = first.json()
    assert first.headers["cache-control"] == "no-store"
    db_session.refresh(records.application)
    assert records.application.stage == "interview"
    event = db_session.scalars(select(StageEvent)).one()
    assert (event.from_stage, event.to_stage, event.actor_id) == (
        "submitted",
        "interview",
        account.id,
    )
    assert event.occurred_at == records.application.stage_entered_at
    assert records.application.owner_id == records.other.id
    assert create(client, records, body={**INTERVIEW, "round": 2}).status_code == 201
    assert count(db_session, Interview) == 2 and count(db_session, StageEvent) == 1
    updated = patch(
        client, f"/interviews/{row['id']}", {"result": "pass", "feedback": "Phản hồi giả"}
    )
    assert updated.status_code == 200 and updated.json()["feedback"] == "Phản hồi giả"
    assert count(db_session, StageEvent) == 1  # Results never reject or move a candidate.
    calendar_response = client.get(f"/api/v1/interviews/{row['id']}/ics")
    assert calendar_response.status_code == 200
    assert calendar_response.headers["cache-control"] == "no-store"
    assert calendar_response.headers["content-type"].startswith("text/calendar")
    assert calendar_response.headers["content-disposition"].endswith('.ics"')
    parsed = Calendar.from_ical(calendar_response.content)
    assert not parsed.errors
    events = parsed.walk("VEVENT")
    assert len(events) == 1 and not events[0].errors
    event = events[0]
    assert event["DTSTART"].params["TZID"] == "Asia/Ho_Chi_Minh"
    assert event.decoded("DTSTART") == datetime(2026, 11, 10, 2, 30, tzinfo=UTC)
    assert event.decoded("DTSTART").hour == 9
    assert event.decoded("DTEND") - event.decoded("DTSTART") == timedelta(minutes=75)
    assert str(event["LOCATION"]) == INTERVIEW["location_or_link"].strip()
    assert str(event["UID"]) == f"{row['id']}@hr-ats.invalid"
    assert "ATTENDEE" not in event and "DESCRIPTION" not in event
    assert all(len(line) <= 75 for line in calendar_response.content.split(b"\r\n"))
    assert calendar_response.content == client.get(f"/api/v1/interviews/{row['id']}/ics").content
    detail = client.get(f"/api/v1/applications/{records.application.id}").json()
    assert len(detail["interviews"]) == 2
    assert detail["interviews"][0]["feedback"] == "Phản hồi giả"
    assert detail["offers"] == [] and detail["placement"] is None
    for activity in db_session.scalars(select(Activity)):
        assert "feedback" not in activity.payload and "interviewers" not in activity.payload
    assert email_outbox == []


def test_offer_draft_sent_accepted_and_placement_are_atomic(
    client, account, records, db_session, email_outbox
):
    sign_in(client)
    assert create(client, records).status_code == 201
    offer = create(client, records, "offers", {"salary": 20000000, "notes": "Ghi chú giả"})
    assert offer.status_code == 201 and offer.json()["sent_at"] is None
    assert count(db_session, StageEvent) == 1
    offer_id = offer.json()["id"]
    sent = patch(client, f"/offers/{offer_id}", {"status": "sent"})
    assert sent.status_code == 200, sent.text
    assert sent.json()["sent_at"] is not None
    assert count(db_session, StageEvent) == 2
    repeated = patch(client, f"/offers/{offer_id}", {"status": "sent"})
    assert repeated.json()["sent_at"] == sent.json()["sent_at"]
    assert count(db_session, StageEvent) == 2
    accepted = patch(client, f"/offers/{offer_id}", {"status": "accepted"})
    assert accepted.status_code == 200 and count(db_session, StageEvent) == 2
    assert patch(client, f"/offers/{offer_id}", {"status": "draft"}).status_code == 409
    placement = create(client, records, "placement", PLACEMENT)
    assert placement.status_code == 201, placement.text
    db_session.refresh(records.application)
    assert records.application.stage == "hired"
    assert count(db_session, StageEvent) == 3
    assert create(client, records, "placement", PLACEMENT).status_code == 409
    assert count(db_session, Placement) == 1
    placement_id = placement.json()["id"]
    invalid = patch(client, f"/placements/{placement_id}", {"start_date": "2028-01-01"})
    assert invalid.status_code == 422
    updated = patch(
        client, f"/placements/{placement_id}", {"status": "completed", "fee_amount": None}
    )
    assert updated.status_code == 200 and updated.json()["fee_amount"] is None
    # Undo moves the stage only; business records and history remain for HR to edit.
    assert (
        client.post(
            f"/api/v1/applications/{records.application.id}/undo", headers=csrf_headers(client)
        ).json()["stage"]
        == "offer"
    )
    assert count(db_session, Placement) == 1 and count(db_session, StageEvent) == 4
    assert create(client, records, "placement", PLACEMENT).status_code == 409
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(
            Placement(application_id=records.application.id, start_date=date(2026, 12, 1))
        )
        db_session.flush()
    assert email_outbox == []


@pytest.mark.parametrize(
    "action,target,body",
    [
        ("interviews", "interview", INTERVIEW),
        ("offers", "offer", {"status": "sent"}),
        ("placement", "hired", PLACEMENT),
    ],
)
def test_no_stage_skipping_or_history_on_invalid_create(
    client, account, records, db_session, action, target, body
):
    records.application.stage = ApplicationStage.new
    db_session.commit()
    sign_in(client)
    response = create(client, records, action, body)
    assert (
        response.status_code == 409
        and response.json()["error"]["code"] == "INVALID_STAGE_TRANSITION"
    )
    assert (
        count(db_session, Interview)
        == count(db_session, Offer)
        == count(db_session, Placement)
        == 0
    )
    assert count(db_session, StageEvent) == count(db_session, Activity) == 0


@pytest.mark.parametrize("kind", ["interview", "offer", "placement"])
def test_pipeline_and_record_roll_back_together(
    client, account, records, db_session, monkeypatch, kind
):
    sign_in(client)
    records.application.stage = {
        "interview": ApplicationStage.submitted,
        "offer": ApplicationStage.interview,
        "placement": ApplicationStage.offer,
    }[kind]
    db_session.commit()
    before = records.application.stage
    if kind in {"interview", "offer"}:

        def fail(*args, **kwargs):
            raise RuntimeError("synthetic private failure")

        monkeypatch.setattr(recruitment, "log_activity", fail)
    else:
        # Fail the record flush after pipeline.move has already added its event.
        from sqlalchemy import event

        def fail_flush(session, context, instances):
            if any(isinstance(row, Placement) for row in session.new):
                raise RuntimeError("synthetic private failure")

        event.listen(db_session, "before_flush", fail_flush)
    response = create(
        client,
        records,
        {"interview": "interviews", "offer": "offers", "placement": "placement"}[kind],
        {"interview": INTERVIEW, "offer": {"status": "sent"}, "placement": PLACEMENT}[kind],
    )
    assert response.status_code == 500 and "synthetic private failure" not in response.text
    db_session.refresh(records.application)
    assert records.application.stage == before
    assert count(db_session, StageEvent) == count(db_session, Activity) == 0
    assert (
        count(db_session, Interview)
        == count(db_session, Offer)
        == count(db_session, Placement)
        == 0
    )


@pytest.mark.parametrize(
    "body",
    [
        {"duration_minutes": 0},
        {"duration_minutes": 1441},
        {"round": 0},
        {"scheduled_at": "2026-11-10T09:30:00"},
        {"interviewers": [" "]},
        {"interviewers": None},
        {"actor_id": str(uuid4())},
        {"result": "fail"},
    ],
)
def test_interview_input_validation(client, account, records, body):
    sign_in(client)
    assert create(client, records, body={**INTERVIEW, **body}).status_code == 422


def test_patches_missing_records_and_nullable_fields(client, account, records):
    sign_in(client)
    row = create(client, records).json()
    path = f"/interviews/{row['id']}"
    for field in ("round", "scheduled_at", "duration_minutes", "result", "interviewers"):
        assert patch(client, path, {field: None}).status_code == 422
    assert (
        patch(
            client, path, {"feedback": None, "location_or_link": None, "interviewers": []}
        ).status_code
        == 200
    )
    assert patch(client, f"/interviews/{uuid4()}", {}).status_code == 404
    assert patch(client, f"/offers/{uuid4()}", {}).status_code == 404
    assert patch(client, f"/placements/{uuid4()}", {}).status_code == 404
    assert create(client, records, "offers", {"salary": -1}).status_code == 422
    assert create(client, records, "offers", {"status": "accepted"}).status_code == 422
    assert (
        create(
            client, records, "placement", {**PLACEMENT, "guarantee_until": "2020-01-01"}
        ).status_code
        == 422
    )


@pytest.mark.parametrize(
    "role,member,status",
    [
        (UserRole.admin, False, 201),
        (UserRole.lead, False, 201),
        (UserRole.recruiter, False, 403),
        (UserRole.recruiter, True, 201),
    ],
)
def test_scope_for_all_record_endpoints(client, account, records, db_session, role, member, status):
    sign_in(client)
    interview = create(client, records).json()
    offer = create(client, records, "offers", {"status": "sent"}).json()
    placement = create(client, records, "placement", PLACEMENT).json()
    records.other.role = role
    if member:
        db_session.add(JobMember(job_id=records.job.id, user_id=records.other.id))
    db_session.commit()
    sign_in(client, records.other.email)
    permitted = status == 201
    for endpoint, row in (("interviews", interview), ("offers", offer), ("placements", placement)):
        assert patch(client, f"/{endpoint}/{row['id']}", {}).status_code == (
            200 if permitted else 403
        )
    assert client.get(f"/api/v1/interviews/{interview['id']}/ics").status_code == (
        200 if permitted else 403
    )
    listed = client.get("/api/v1/interviews?mine=false").json()
    assert listed["total"] == int(permitted)
    # Application ownership alone does not grant Job access.
    assert create(client, records, "offers", {}).status_code == status
    if member:
        db_session.delete(db_session.scalars(select(JobMember)).one())
        db_session.commit()
        assert patch(client, f"/interviews/{interview['id']}", {}).status_code == 403


@pytest.mark.parametrize("hidden", ["application", "candidate", "merged", "expired", "interview"])
def test_hidden_records_are_unavailable(client, account, records, db_session, hidden):
    sign_in(client)
    row = create(client, records).json()
    if hidden == "application":
        records.application.deleted_at = datetime.now(UTC)
    elif hidden == "candidate":
        records.candidate.deleted_at = datetime.now(UTC)
    elif hidden == "merged":
        records.candidate.merged_into_id = records.candidate.id
    elif hidden == "expired":
        records.candidate.retention_until = date(2000, 1, 1)
    else:
        db_session.get(Interview, row["id"]).deleted_at = datetime.now(UTC)
    db_session.commit()
    assert patch(client, f"/interviews/{row['id']}", {}).status_code == 404
    assert client.get(f"/api/v1/interviews/{row['id']}/ics").status_code == 404
    assert client.get("/api/v1/interviews?mine=false").json()["total"] == 0


def test_list_interval_vietnam_midnight_mine_and_pagination(client, account, records, db_session):
    sign_in(client)
    for timestamp in (
        "2026-11-09T23:59:59+07:00",
        "2026-11-10T00:00:00+07:00",
        "2026-11-11T00:00:00+07:00",
    ):
        assert (
            create(client, records, body={**INTERVIEW, "scheduled_at": timestamp}).status_code
            == 201
        )
    assert client.get("/api/v1/interviews").json()["total"] == 0  # Application belongs to other.
    query = "/api/v1/interviews?from=2026-11-10&to=2026-11-11&mine=false"
    response = client.get(query)
    assert response.status_code == 200 and response.json()["total"] == 1
    assert client.get("/api/v1/interviews?mine=false&page_size=1&page=2").json()["total"] == 3
    assert len(client.get("/api/v1/interviews?mine=false&page_size=1&page=2").json()["items"]) == 1
    assert client.get("/api/v1/interviews?from=2026-11-11&to=2026-11-10").status_code == 422
    assert client.get("/api/v1/interviews?from=2026-11-10T09:00:00").status_code == 422


def test_auth_csrf_and_origin(client, account, records):
    assert create(client, records).status_code == 401
    sign_in(client)
    path = f"/api/v1/applications/{records.application.id}/interviews"
    assert client.post(path, json=INTERVIEW).status_code == 403
    assert (
        client.post(
            path,
            json=INTERVIEW,
            headers={**csrf_headers(client), "Origin": "https://invalid.invalid"},
        ).status_code
        == 403
    )


def test_simultaneous_placements_have_one_winner(empty_engine):
    with empty_engine.begin() as connection:
        config = migration_config()
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    from app.models import User

    with Session(empty_engine) as session:
        actor = User(
            email="concurrency@example.invalid",
            full_name="Tài khoản giả",
            role=UserRole.admin,
            password_hash="unused-synthetic",
        )
        session.add(actor)
        session.flush()
        data = seed_records(session, actor)
        data.application.stage = ApplicationStage.offer
        session.commit()
        actor_id, application_id = actor.id, data.application.id
    barrier = Barrier(2)

    def create_one():
        with Session(empty_engine) as session:
            actor = session.get_one(User, actor_id)
            barrier.wait(timeout=10)
            try:
                recruitment.create_placement(
                    session, actor, application_id, PlacementCreate(start_date=date(2026, 12, 1))
                )
                return "created"
            except AppError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: create_one(), range(2)))
    assert sorted(outcomes) == ["PLACEMENT_EXISTS", "created"]
    with Session(empty_engine) as session:
        assert count(session, Placement) == count(session, StageEvent) == 1
