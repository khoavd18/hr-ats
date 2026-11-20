"""Independent hand-computed T26 dataset. All people/files are synthetic.

Period: Nov 1 00:00 <= t < Nov 4 00:00, UTC+7. A has repeated submissions;
B entered screening just before the window and enters hired exactly at its end.
No mocked SQL, clock reads or expected values copied from production queries.
"""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import pytest
from openpyxl import load_workbook
from sqlalchemy import event, select

from app.core.errors import AppError
from app.models import (
    Activity,
    AiFeedback,
    Application,
    Candidate,
    CvFile,
    HiringUnit,
    Interview,
    Job,
    JobMember,
    Offer,
    Placement,
    StageEvent,
    User,
)
from app.models.enums import ApplicationStage, HiringUnitKind, JobStatus
from app.models.users import UserRole
from app.reports import queries, service
from app.schemas.reports import ReportInput
from tests.auth_helpers import sign_in


def at(value):
    return datetime.fromisoformat(f"2026-{value}+07:00").astimezone(UTC)


START = at("11-01T00:00:00")
END = at("11-04T00:00:00")
NOW = at("11-02T12:00:00")
PARAMS = {"from": "2026-11-01", "to": "2026-11-04"}
ENDPOINTS = ["summary", "funnel", "recruiters", "ai-agreement", "export.xlsx"]


def add(session, cls, **kwargs):
    row = cls(**kwargs)
    session.add(row)
    session.flush()
    return row


@pytest.fixture
def dataset(db_session, account):
    session = db_session
    a, b = [
        add(
            session,
            User,
            email=f"t26-{key}@example.invalid",
            full_name=f"Recruiter giả {key}",
            password_hash=account.password_hash,
            role=UserRole.recruiter,
        )
        for key in ("a", "b")
    ]
    u1, u2 = [
        add(session, HiringUnit, name=f"Đơn vị giả {key}", kind=HiringUnitKind.client)
        for key in ("a", "b")
    ]
    j1 = add(
        session,
        Job,
        title="Job giả A",
        description="",
        owner_id=a.id,
        hiring_unit_id=u1.id,
        opened_at=at("10-30T00:00:00"),
        deadline=date(2026, 11, 1),
        headcount=3,
        status=JobStatus.open,
    )
    j2 = add(
        session,
        Job,
        title="Job giả B",
        description="",
        owner_id=b.id,
        hiring_unit_id=u2.id,
        opened_at=at("10-29T00:00:00"),
        deadline=date(2026, 11, 1),
        headcount=1,
        status=JobStatus.open,
    )
    membership = add(session, JobMember, job_id=j2.id, user_id=a.id)
    apps = []
    for key, job, owner, created in [
        ("A1", j1, a, "10-31T00:00:00"),
        ("A2", j1, a, "11-01T00:00:00"),
        ("B1", j2, b, "10-31T00:00:00"),
        ("B2", j2, b, "11-03T00:00:00"),
    ]:
        candidate = add(
            session, Candidate, full_name=f"Ứng viên giả {key}", retention_until=date(2020, 1, 1)
        )
        apps.append(
            add(
                session,
                Application,
                candidate_id=candidate.id,
                job_id=job.id,
                owner_id=owner.id,
                created_at=at(created),
            )
        )
    a1, a2, b1, b2 = apps

    def stage(app, old, new, when):
        return add(
            session,
            StageEvent,
            application_id=app.id,
            from_stage=old,
            to_stage=new,
            actor_id=account.id,
            occurred_at=at(when),
            created_at=at(when),
        )

    stage(a1, None, "new", "10-31T00:00:00")
    stage(a1, "new", "screening", "11-01T00:00:00")
    stage(a1, "screening", "submitted", "11-02T00:00:00")
    stage(a1, "submitted", "screening", "11-02T12:00:00")
    stage(a1, "screening", "submitted", "11-03T00:00:00")
    stage(a1, "submitted", "interview", "11-03T12:00:00")
    stage(a2, "new", "rejected", "11-01T12:00:00")
    stage(b1, None, "new", "10-31T00:00:00")
    stage(b1, "new", "screening", "10-31T23:59:59.999999")
    stage(b1, "screening", "submitted", "11-01T00:00:00")
    stage(b1, "submitted", "interview", "11-02T00:00:00")
    stage(b1, "interview", "offer", "11-03T00:00:00")
    stage(b1, "offer", "hired", "11-04T00:00:00")

    for app, when in [
        (a1, START),
        (a2, NOW),
        (b1, at("11-03T00:00:00")),
        (b1, START - timedelta(microseconds=1)),
        (a1, END),
    ]:
        add(
            session,
            Interview,
            application_id=app.id,
            round=1,
            scheduled_at=when,
            duration_minutes=60,
        )
    for app, sent in [(a1, START), (b1, at("11-03T00:00:00")), (a2, None), (b2, END)]:
        add(session, Offer, application_id=app.id, status="sent" if sent else "draft", sent_at=sent)
    for app, when, fee in [
        (a1, START, 100),
        (a2, at("11-03T00:00:00"), 0),
        (b1, at("11-02T00:00:00"), 300),
        (b2, at("11-03T00:00:00"), None),
    ]:
        add(
            session,
            Placement,
            application_id=app.id,
            start_date=date(2027, 1, 1),
            fee_amount=fee,
            created_at=when,
        )

    files = []
    for uploader, job, when in [
        (a, j1, START),
        (a, j2, at("11-02T00:00:00")),
        (None, j1, at("11-03T00:00:00")),
        (None, None, at("11-03T00:00:00")),
        (b, j2, START),
        (a, j1, START - timedelta(microseconds=1)),
        (a, j1, END),
    ]:
        files.append(
            add(
                session,
                CvFile,
                storage_key="synthetic",
                original_filename="fake.pdf",
                mime_type="application/pdf",
                size_bytes=1,
                sha256=uuid4().hex * 2,
                uploaded_by=uploader.id if uploader else None,
                job_id=job.id if job else None,
                created_at=when,
            )
        )
    for app, user, verdict, when in [
        (a1, a, "agree", START),
        (a2, b, "disagree", NOW),
        (b1, a, "agree", NOW),
        (b1, b, "agree", NOW),
        (b1, account, "agree", NOW),
        (a1, b, "disagree", START - timedelta(microseconds=1)),
        (a1, account, "disagree", END),
    ]:
        add(
            session,
            AiFeedback,
            application_id=app.id,
            user_id=user.id,
            verdict=verdict,
            created_at=when,
        )
    for actor, job, kind in [
        (a, j1, "call"),
        (a, None, "call"),
        (b, j2, "note"),
        (None, None, "email_sent"),
        (account, None, "task_done"),
    ]:
        add(
            session,
            Activity,
            actor_id=actor.id if actor else None,
            type=kind,
            job_id=job.id if job else None,
            occurred_at=START,
        )
    session.commit()
    return SimpleNamespace(
        a=a, b=b, j1=j1, j2=j2, u1=u1, u2=u2, apps=apps, files=files, membership=membership
    )


def report(db_session, account, **extra):
    return service.summary(db_session, account, ReportInput.model_validate(PARAMS | extra), now=NOW)


def test_all_thirteen_kpis_match_independent_hand_calculation(db_session, account, dataset):
    result = report(db_session, account)
    m = result.metrics
    assert (m.new_cvs, m.screened, m.submitted, m.offers, m.placements) == (5, 2, 3, 2, 4)
    assert m.interviews.model_dump() == {"total": 3, "elapsed": 1, "upcoming": 2}
    assert [r.count for r in m.funnel] == [2, 1, 2, 2, 1, 0, 1, 0]
    assert [r.conversion_rate for r in m.funnel] == [0.5, 2, 1, 0.5, 0, None, None, None]
    assert m.time_to_fill.model_dump() == {"days": 4, "sample_count": 4, "excluded_count": 0}
    assert [
        (m.stage_duration[s].days, m.stage_duration[s].sample_count) for s in ApplicationStage
    ] == [
        (0.75, 2),
        (0.5, 3),
        (0.5, 3),
        (1, 1),
        (None, 0),
        (None, 0),
        (None, 0),
        (None, 0),
    ]
    assert m.overdue_jobs == 1
    assert m.placement_revenue.model_dump() == {"amount": 400, "known_count": 3, "missing_count": 1}
    assert m.ai_agreement.model_dump() == {"agree": 4, "disagree": 1, "total": 5, "rate": 0.8}
    assert {kind: n for kind, n in m.activities.items() if n} == {
        "call": 2,
        "note": 1,
        "email_sent": 1,
        "task_done": 1,
    }
    assert [(r.date.isoformat(), r.count) for r in result.new_cvs_by_day] == [
        ("2026-11-01", 2),
        ("2026-11-02", 1),
        ("2026-11-03", 2),
    ]
    assert result.period.definition_status == "draft" and result.period.as_of == NOW


def test_grouped_totals_reconcile_without_averaging_ratios_or_medians(db_session, account, dataset):
    rows = service.recruiters(db_session, account, ReportInput.model_validate(PARAMS)).items
    grouped = {row.recruiter_id: row.metrics for row in rows}
    a, b = grouped[dataset.a.id], grouped[dataset.b.id]
    assert (a.new_cvs, b.new_cvs, grouped[None].new_cvs) == (3, 1, 1)
    assert (a.screened, b.screened, a.submitted, b.submitted) == (2, 0, 2, 1)
    assert (a.ai_agreement.rate, b.ai_agreement.rate) == (0.5, 1)
    assert (a.time_to_fill.days, b.time_to_fill.days) == (3, 4.5)
    total = report(db_session, account).metrics
    assert total.time_to_fill.days == 4  # Not (3 + 4.5) / 2.
    assert total.ai_agreement.rate == 0.8  # Not (0.5 + 1) / 2.
    for key in ("new_cvs", "screened", "submitted", "offers", "placements", "overdue_jobs"):
        assert sum(getattr(row.metrics, key) for row in rows) == getattr(total, key)
    assert sum(sum(row.metrics.activities.values()) for row in rows) == 5


def test_filters_and_current_job_access_do_not_expand_recruiter_scope(db_session, dataset):
    a = dataset.a
    own = report(db_session, a).metrics
    assert (own.new_cvs, own.placements, own.ai_agreement.total) == (3, 2, 2)
    assert report(db_session, a, hiring_unit_id=dataset.u2.id).metrics.new_cvs == 1
    assert report(db_session, a, job_id=dataset.j2.id).metrics.placements == 0
    db_session.delete(dataset.membership)
    db_session.commit()
    assert report(db_session, a).metrics.new_cvs == 2
    assert report(db_session, a, hiring_unit_id=dataset.u2.id).metrics.new_cvs == 0
    with pytest.raises(AppError) as failure:
        report(db_session, a, job_id=dataset.j2.id)
    assert failure.value.status == 403


def test_empty_zero_and_missing_are_distinct(db_session, account, dataset):
    empty_report = report(db_session, account, hiring_unit_id=uuid4())
    assert [day.count for day in empty_report.new_cvs_by_day] == [0, 0, 0]
    empty = empty_report.metrics
    assert (empty.new_cvs, empty.screened, empty.placements, empty.overdue_jobs) == (0, 0, 0, 0)
    assert empty.time_to_fill.days is None and empty.time_to_fill.sample_count == 0
    assert empty.ai_agreement.rate is None and empty.ai_agreement.total == 0
    assert empty.placement_revenue.amount is None and empty.placement_revenue.missing_count == 0
    assert all(row.conversion_rate is None for row in empty.funnel)
    # A's known fees are 100 and an explicit zero; B has one missing value.
    for row in db_session.scalars(select(Placement).where(Placement.fee_amount.is_not(None))):
        row.fee_amount = 0
    db_session.commit()
    fees = report(db_session, account).metrics.placement_revenue
    assert (fees.amount, fees.known_count, fees.missing_count) == (0, 3, 1)
    for row in db_session.scalars(select(Placement)):
        row.fee_amount = None
    db_session.commit()
    fees = report(db_session, account).metrics.placement_revenue
    assert (fees.amount, fees.known_count, fees.missing_count) == (None, 0, 4)


def test_time_to_fill_excludes_unknown_and_reopened_after_placement(db_session, account, dataset):
    dataset.j1.opened_at = None
    dataset.j2.opened_at = END
    db_session.commit()
    metric = report(db_session, account).metrics.time_to_fill
    assert metric.days is None and metric.sample_count == 0 and metric.excluded_count == 4


def test_zero_duration_and_implicit_entry_precedes_same_instant_event(db_session, account, dataset):
    row = db_session.scalars(
        select(StageEvent).where(StageEvent.application_id == dataset.apps[1].id)
    ).one()
    # A2's synthetic entry ID sorts after this ID. Entry order must not depend on UUIDs.
    from uuid import UUID

    row.id = UUID(int=1)
    row.occurred_at = row.created_at = START
    db_session.commit()
    durations = report(db_session, account).metrics.stage_duration
    assert durations["new"].days == 0.5 and durations["new"].sample_count == 2
    assert durations["rejected"].days is None


def test_deadline_is_vietnam_snapshot_and_filled_uses_whole_job(db_session, account, dataset):
    params = ReportInput.model_validate(PARAMS)
    before = service.summary(db_session, account, params, now=at("11-01T23:59:59.999999"))
    midnight = service.summary(db_session, account, params, now=at("11-02T00:00:00"))
    assert before.metrics.overdue_jobs == 0 and midnight.metrics.overdue_jobs == 1
    # A owns Job 1, but one of its placements is attributed to B. It still fills a seat.
    dataset.apps[1].owner_id = dataset.b.id
    dataset.j1.headcount = 2
    db_session.commit()
    assert report(db_session, account, recruiter_id=dataset.a.id).metrics.overdue_jobs == 0
    dataset.j1.headcount = 3
    dataset.j1.status = JobStatus.closed
    db_session.commit()
    assert report(db_session, account).metrics.overdue_jobs == 0


@pytest.mark.parametrize(
    "model", [CvFile, StageEvent, Interview, Offer, Placement, AiFeedback, Activity]
)
def test_soft_deleted_records_are_excluded(db_session, account, dataset, model):
    for row in db_session.scalars(select(model)):
        row.deleted_at = NOW
    db_session.commit()
    m = report(db_session, account).metrics
    if model == CvFile:
        assert m.new_cvs == 0
    elif model == StageEvent:
        assert m.screened == m.submitted == 0
        assert all(row.sample_count == 0 for row in m.stage_duration.values())
    elif model == Interview:
        assert m.interviews.total == 0
    elif model == Offer:
        assert m.offers == 0
    elif model == Placement:
        assert m.placements == 0 and m.time_to_fill.days is None
        assert m.placement_revenue.amount is None
    elif model == AiFeedback:
        assert m.ai_agreement.total == 0
    else:
        assert sum(m.activities.values()) == 0


def test_deleted_application_excludes_all_children(db_session, account, dataset):
    for row in dataset.apps:
        row.deleted_at = NOW
    db_session.commit()
    m = report(db_session, account).metrics
    assert m.screened == m.submitted == m.offers == m.placements == m.interviews.total == 0
    assert m.ai_agreement.total == 0 and m.time_to_fill.days is None
    assert all(row.count == 0 for row in m.funnel)
    assert m.new_cvs == 5  # CV intake is its own fact, not an Application join.


@pytest.mark.parametrize("boundary", [START - timedelta(microseconds=1), END])
def test_every_flow_has_half_open_boundary_including_placements(
    db_session, account, dataset, boundary
):
    # Exact start is included for every timestamp-based KPI; exact end is excluded.
    for model, field in [
        (CvFile, "created_at"),
        (StageEvent, "occurred_at"),
        (Interview, "scheduled_at"),
        (Offer, "sent_at"),
        (Placement, "created_at"),
        (AiFeedback, "created_at"),
        (Activity, "occurred_at"),
    ]:
        for row in db_session.scalars(select(model)):
            if model != Offer or row.status != "draft":
                setattr(row, field, boundary)
    for app in dataset.apps:
        app.created_at = boundary
    db_session.commit()
    m = report(db_session, account).metrics
    assert m.new_cvs == m.screened == m.submitted == m.offers == m.placements == 0
    assert m.interviews.total == m.ai_agreement.total == sum(m.activities.values()) == 0
    assert m.time_to_fill.days is None and all(r.count == 0 for r in m.funnel)


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_endpoints_require_login(client, endpoint):
    assert client.get(f"/api/v1/reports/{endpoint}", params=PARAMS).status_code == 401


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_recruiter_cannot_request_another_recruiter(client, account, dataset, db_session, endpoint):
    account.role = UserRole.recruiter
    db_session.commit()
    sign_in(client)
    response = client.get(
        f"/api/v1/reports/{endpoint}", params=PARAMS | {"recruiter_id": dataset.a.id}
    )
    assert response.status_code == 403


@pytest.mark.parametrize(
    "extra",
    [
        {"from": "2026-11-04"},
        {"to": "2026-11-01"},
        {"to": "2028-01-01"},
        {"from": "bad"},
        {"from": "2026-11-01T12:00:00"},
        {"from": "2026-11-01T00:00:00+07:00"},
        {"from": "0001-01-01", "to": "0001-01-02"},
        {"recruiter_id": "bad"},
        {"job_id": "bad"},
        {"hiring_unit_id": "bad"},
        {"unknown": "ignored?"},
    ],
)
def test_query_validation(client, account, extra):
    sign_in(client)
    response = client.get("/api/v1/reports/summary", params=PARAMS | extra)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_api_contract_consistency_no_pii_and_vietnam_dates(client, account, dataset, monkeypatch):
    monkeypatch.setenv("TZ", "UTC")
    sign_in(client)
    responses = {key: client.get(f"/api/v1/reports/{key}", params=PARAMS) for key in ENDPOINTS}
    for response in responses.values():
        assert response.status_code == 200, response.text[:500]
        assert response.headers["cache-control"] == "no-store"
    summary = responses["summary"].json()
    assert summary["metrics"]["new_cvs"] == 5
    assert responses["funnel"].json()["stages"] == summary["metrics"]["funnel"]
    assert responses["ai-agreement"].json()["agreement"] == summary["metrics"]["ai_agreement"]
    assert summary["period"]["definition_status"] == "draft"
    for key in ENDPOINTS[:-1]:
        text = responses[key].text
        assert "Ứng viên giả" not in text and "example.invalid" not in text
        assert "candidate_id" not in text and "application_id" not in text
    book = load_workbook(BytesIO(responses["export.xlsx"].content))
    assert book["Tổng hợp"].cell(2, 1).value == 5
    assert book["Tổng hợp"].cell(2, 13).value == 400
    assert book["Tổng hợp"].cell(2, 19).value == 0.8
    assert book["CV theo ngày"].max_row == 4
    assert [book["CV theo ngày"].cell(i, 2).value for i in (2, 3, 4)] == [2, 1, 2]
    assert book["Phễu"].cell(3, 5).value == 2  # Flow ratio may exceed 100%.
    assert book["Tổng hợp"].freeze_panes == "A2"


@pytest.mark.parametrize("prefix", ["=", "+", "-", "@", "\t=", "\x00="])
def test_excel_safely_preserves_recruiter_names(client, account, dataset, db_session, prefix):
    # PostgreSQL text forbids NUL, but can contain other XML-illegal controls.
    prefix = prefix.replace("\x00", "\x01")
    dataset.a.full_name = prefix + 'HYPERLINK("https://example.invalid","synthetic")'
    db_session.commit()
    sign_in(client)
    response = client.get("/api/v1/reports/export.xlsx", params=PARAMS)
    assert response.status_code == 200
    book = load_workbook(BytesIO(response.content), data_only=False)
    matches = [
        cell
        for row in book["Theo người phụ trách"]
        for cell in row
        if cell.value == dataset.a.full_name.replace("\x01", "")
    ]
    assert len(matches) == 1 and matches[0].data_type == "s"
    assert not any(cell.data_type == "f" for sheet in book for row in sheet for cell in row)


def test_grouped_query_count_does_not_grow_with_recruiter_roster(db_session, account, dataset):
    params = ReportInput.model_validate(PARAMS)
    counts = []

    def track(*args):
        counts.append(1)

    for iteration in range(2):
        if iteration:
            for index in range(10):
                add(
                    db_session,
                    User,
                    email=f"t26-idle-{index}@example.invalid",
                    full_name=f"Recruiter rỗng {index}",
                    role=UserRole.recruiter,
                    password_hash=account.password_hash,
                )
            db_session.flush()
        db_session.refresh(account)
        connection = db_session.connection()
        event.listen(connection, "before_cursor_execute", track)
        counts.clear()
        try:
            service.recruiters(db_session, account, params)
        finally:
            event.remove(connection, "before_cursor_execute", track)
        if iteration == 0:
            initial = len(counts)
        else:
            assert len(counts) == initial


def test_direct_queries_authorize_and_inactive_history_stays_visible(db_session, account, dataset):
    start, end, filters, _ = queries.prepare(
        db_session, dataset.a, ReportInput.model_validate(PARAMS)
    )
    with pytest.raises(AppError):
        queries.new_cvs(db_session, start, end, replace(filters, recruiter_id=dataset.b.id))
    dataset.b.is_active = False
    db_session.commit()
    team = service.recruiters(db_session, account, ReportInput.model_validate(PARAMS))
    assert (
        next(row for row in team.items if row.recruiter_id == dataset.b.id).metrics.placements == 2
    )
