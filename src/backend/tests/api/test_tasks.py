"""T25: real PostgreSQL, controlled clock and in-memory SMTP; synthetic data only."""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import func, select

from app.models import Activity, EmailMessage, Interview, JobMember, Task
from app.models.enums import ActivityType, ApplicationStage, TaskStatus
from app.models.users import UserRole
from app.services import tasks
from app.workers import email, reminders
from tests.api.test_pipeline import seed_records
from tests.auth_helpers import csrf_headers, sign_in


@pytest.fixture
def records(db_session, account):
    data = seed_records(db_session, account)
    data.application.owner_id = account.id
    db_session.commit()
    return data


def add(session, actor, **kwargs):
    row = Task(title="Việc giả T25", assignee_id=actor.id, created_by=actor.id, **kwargs)
    session.add(row)
    session.flush()
    return row


def post(client, body):
    return client.post("/api/v1/tasks", json=body, headers=csrf_headers(client))


def patch(client, row_id, body):
    return client.patch(f"/api/v1/tasks/{row_id}", json=body, headers=csrf_headers(client))


def test_task_crud_completion_idempotency_and_reopen(client, account, records, db_session):
    sign_in(client)
    created = post(
        client,
        {
            "title": "  Việc giả  ",
            "application_id": str(records.application.id),
            "due_at": "2026-11-09T08:00:00+07:00",
        },
    )
    assert created.status_code == 201, created.text
    row = created.json()
    assert row["title"] == "Việc giả" and row["job_id"] == str(records.job.id)
    assert row["created_by"] == row["assignee_id"] == str(account.id)
    assert row["status"] == "todo" and row["completed_at"] is None
    assert created.headers["cache-control"] == "no-store"
    done = patch(client, row["id"], {"status": "done"})
    assert done.status_code == 200 and done.json()["completed_at"]
    assert (
        patch(client, row["id"], {"status": "done"}).json()["completed_at"]
        == done.json()["completed_at"]
    )
    activities = list(db_session.scalars(select(Activity).where(Activity.type == "task_done")))
    assert len(activities) == 1 and activities[0].payload == {"task_id": row["id"]}
    assert activities[0].application_id == records.application.id
    assert activities[0].candidate_id == records.candidate.id
    assert client.get("/api/v1/tasks").json()["total"] == 0
    assert client.get("/api/v1/tasks?status=done").json()["total"] == 1
    reopened = patch(client, row["id"], {"status": "doing", "due_at": None})
    assert reopened.status_code == 200 and reopened.json()["completed_at"] is None
    assert reopened.json()["due_at"] is None
    assert records.application.stage == "new"


@pytest.mark.parametrize(
    "body",
    [
        {"title": " "},
        {"title": "x", "completed_at": "2026-01-01"},
        {"title": "x", "status": "done"},
        {"title": "x", "created_by": "spoof"},
        {"title": "x", "due_at": "2026-11-09T08:00:00"},
        {"title": "x" * 201},
    ],
)
def test_input_validation(client, account, body):
    sign_in(client)
    assert post(client, body).status_code == 422


def test_assignee_scope_links_and_membership_revocation(client, account, records, db_session):
    account.role = UserRole.recruiter
    db_session.commit()
    sign_in(client)
    assert post(client, {"title": "x", "assignee_id": str(records.other.id)}).status_code == 403
    assert client.get("/api/v1/tasks?mine=false").status_code == 403
    task = post(client, {"title": "x", "job_id": str(records.job.id)}).json()
    other_task = add(db_session, records.other)
    db_session.commit()
    assert patch(client, other_task.id, {"status": "done"}).status_code == 403
    records.job.owner_id = records.other.id
    db_session.add(JobMember(job_id=records.job.id, user_id=account.id))
    db_session.commit()
    assert client.get("/api/v1/tasks").json()["total"] == 1
    member = db_session.scalars(select(JobMember)).one()
    db_session.delete(member)
    db_session.commit()
    assert client.get("/api/v1/tasks").json()["total"] == 0
    assert patch(client, task["id"], {"status": "done"}).status_code == 403
    assert (
        post(client, {"title": "x", "application_id": str(records.application.id)}).status_code
        == 403
    )
    assert (
        client.get(f"/api/v1/tasks/application-options?job_id={records.job.id}").status_code == 403
    )


def test_completion_rolls_back_when_activity_fails(client, account, db_session, monkeypatch):
    row = add(db_session, account)
    db_session.commit()
    sign_in(client)

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(tasks, "log_activity", fail)
    assert patch(client, row.id, {"status": "done"}).status_code == 500
    db_session.expire_all()
    assert row.status == "todo" and row.completed_at is None


@pytest.mark.parametrize(
    "age,activity_age,expected", [(3, None, 0), (3.01, None, 1), (4, 2, 0), (5, 3, 0), (5, 3.01, 1)]
)
def test_screening_rule_boundaries_and_open_duplicate(
    db_session, account, records, age, activity_age, expected
):
    now = datetime.now(UTC)
    records.application.stage = ApplicationStage.screening
    records.application.stage_entered_at = now - timedelta(days=age)
    if activity_age is not None:
        db_session.add(
            Activity(
                type=ActivityType.call,
                actor_id=account.id,
                application_id=records.application.id,
                occurred_at=now - timedelta(days=activity_age),
            )
        )
    db_session.commit()
    assert reminders.generate(db_session, now) == expected
    assert reminders.generate(db_session, now) == 0
    rows = list(db_session.scalars(select(Task)))
    assert len(rows) == expected
    if expected:
        assert rows[0].title == tasks.CONTACT
        assert rows[0].assignee_id == account.id and rows[0].due_at == now
        rows[0].status = TaskStatus.doing
        db_session.commit()
        assert reminders.generate(db_session, now) == 0


@pytest.mark.parametrize(
    "extra,result,stage,expected",
    [
        (0, "pending", "interview", 0),
        (1, "pending", "interview", 1),
        (1, "pass", "interview", 0),
        (1, "fail", "interview", 0),
        (1, "no_show", "interview", 0),
        (1, "pending", "hired", 0),
    ],
)
def test_interview_rule_uses_end_time_and_pending_result(
    db_session, account, records, extra, result, stage, expected
):
    now = datetime.now(UTC)
    records.application.stage = stage
    db_session.add(
        Interview(
            application_id=records.application.id,
            round=1,
            scheduled_at=now - timedelta(days=1, minutes=60, seconds=extra),
            duration_minutes=60,
            result=result,
        )
    )
    db_session.commit()
    assert reminders.generate(db_session, now) == expected
    assert reminders.generate(db_session, now) == 0
    if expected:
        row = db_session.scalars(select(Task)).one()
        assert row.title == tasks.RESULT and row.application_id == records.application.id


def test_manual_open_task_blocks_rule_and_closed_allows_new(db_session, account, records):
    now = datetime.now(UTC)
    records.application.stage = "screening"
    records.application.stage_entered_at = now - timedelta(days=4)
    row = add(db_session, account, application_id=records.application.id, job_id=records.job.id)
    row.title = tasks.CONTACT
    db_session.commit()
    assert reminders.generate(db_session, now) == 0
    row.status = "cancelled"
    db_session.commit()
    assert reminders.generate(db_session, now) == 1


@pytest.mark.parametrize("hidden", ["deleted", "expired", "merged", "inactive", "lost_access"])
def test_rules_ignore_ineligible_records(db_session, account, records, hidden):
    now = datetime.now(UTC)
    records.application.stage = "screening"
    records.application.stage_entered_at = now - timedelta(days=4)
    if hidden == "deleted":
        records.application.deleted_at = now
    if hidden == "expired":
        records.candidate.retention_until = now.date() - timedelta(days=1)
    if hidden == "merged":
        records.candidate.merged_into_id = records.candidate.id
    if hidden == "inactive":
        account.is_active = False
    if hidden == "lost_access":
        account.role = UserRole.recruiter
        records.job.owner_id = records.other.id
    db_session.commit()
    assert reminders.generate(db_session, now) == 0


@pytest.fixture
def reminder_runtime(db_session, monkeypatch):
    @contextmanager
    def session():
        yield db_session

    monkeypatch.setattr(reminders, "worker_session", session)
    monkeypatch.setattr(email, "worker_session", session)


def test_reminders_only_due_assignees_and_daily_replay(
    db_session, account, records, reminder_runtime, email_outbox
):
    now = datetime.now(UTC)
    start, end = tasks.day_bounds(now)
    for due in (start - timedelta(days=1), end - timedelta(seconds=1)):
        row = add(db_session, account, due_at=due)
        row.title = "Việc giả <script>không chạy</script>"
    add(db_session, records.other, due_at=end)  # Tomorrow, even if the server's UTC date differs.
    add(db_session, records.other)  # No deadline never triggers mail.
    done = add(db_session, records.other, due_at=now, status="done", completed_at=now)
    db_session.commit()
    reminders.remind_due_tasks.run()
    assert len(email_outbox) == 1 and email_outbox[0]["To"] == account.email
    html = email_outbox[0].get_body(preferencelist=("html",)).get_content()
    assert "&lt;script&gt;" in html and "<script>" not in html
    assert html.count("<li>") == 2
    reminders.remind_due_tasks.run()
    assert len(email_outbox) == 1
    assert db_session.scalar(select(func.count()).select_from(EmailMessage)) == 1
    assert done.status == "done"


@pytest.mark.parametrize("change", ["done", "inactive", "membership", "recipient"])
def test_reminder_worker_rechecks_before_smtp(
    db_session, account, records, reminder_runtime, email_outbox, change
):
    row = add(db_session, account, due_at=datetime.now(UTC), job_id=records.job.id)
    db_session.commit()
    queued = reminders.queue_reminders(db_session, datetime.now(UTC))
    assert len(queued) == 1
    if change == "done":
        row.status, row.completed_at = "done", datetime.now(UTC)
    if change == "inactive":
        account.is_active = False
    if change == "membership":
        account.role = UserRole.recruiter
        records.job.owner_id = records.other.id
    if change == "recipient":
        account.email = "changed@example.invalid"
    db_session.commit()
    email.send_email_message.run(*queued[0])
    assert email_outbox == []


def test_reminder_publish_recovery_and_smtp_retry(
    db_session, account, reminder_runtime, email_outbox, monkeypatch
):
    add(db_session, account, due_at=datetime.now(UTC))
    db_session.commit()
    args = reminders.queue_reminders(db_session, datetime.now(UTC))
    assert reminders.queue_reminders(db_session, datetime.now(UTC)) == args

    def fail(*args):
        raise RuntimeError("synthetic SMTP error")

    original = email.deliver
    monkeypatch.setattr(email, "deliver", fail)
    assert email.send_email_message.apply(args=list(args[0])).successful()
    row = db_session.get(EmailMessage, UUID(args[0][0]))
    assert row.status == "failed" and row.scheduled_for and "synthetic" not in row.error
    monkeypatch.setattr(email, "deliver", original)
    row.scheduled_for = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()
    email.send_email_message.run(str(row.id), row.message_id, row.scheduled_for.isoformat(), 1)
    assert len(email_outbox) == 1 and row.status == "sent"


def test_overview_scope_and_unseen_cv(client, account, records, db_session):
    now = datetime.now(UTC)
    start, end = tasks.day_bounds(now)
    records.job.status = "open"
    records.job.deadline = start.date() + timedelta(days=7)
    add(db_session, account, due_at=end - timedelta(seconds=1))
    add(db_session, account, due_at=end)
    for scheduled in (start, end, end + timedelta(days=1)):
        db_session.add(
            Interview(
                application_id=records.application.id,
                round=1,
                scheduled_at=scheduled,
                duration_minutes=60,
            )
        )
    db_session.commit()
    sign_in(client)
    response = client.get("/api/v1/overview")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["today_tasks"]["total"] == 1
    assert data["interview_total"] == 2 and data["job_total"] == data["unseen_cv_count"] == 1
    assert "email" not in str(data["interviews"])
    assert client.get(f"/api/v1/applications/{records.application.id}").status_code == 200
    assert client.get("/api/v1/overview").json()["unseen_cv_count"] == 0
    account.role = UserRole.recruiter
    records.job.owner_id = records.other.id
    db_session.commit()
    sign_in(client)
    data = client.get("/api/v1/overview").json()
    assert data["interview_total"] == data["job_total"] == 0


def test_auth_csrf_and_pagination(client, account, db_session):
    assert client.get("/api/v1/tasks").status_code == 401
    assert client.get("/api/v1/overview").status_code == 401
    sign_in(client)
    assert client.post("/api/v1/tasks", json={"title": "x"}).status_code == 403
    for i in range(3):
        add(db_session, account, due_at=datetime.now(UTC) + timedelta(days=i))
    db_session.commit()
    data = client.get("/api/v1/tasks?page_size=1&page=2").json()
    assert data["total"] == 3 and len(data["items"]) == 1
    assert client.get("/api/v1/tasks?page=0").status_code == 422
    assert client.get("/api/v1/tasks?due_before=2026-11-09T08:00:00").status_code == 422


def test_two_generators_create_one_open_task(empty_engine):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from alembic import command
    from sqlalchemy.orm import Session

    from app.models import User
    from tests.conftest import migration_config

    with empty_engine.begin() as connection:
        config = migration_config()
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    now = datetime.now(UTC)
    with Session(empty_engine) as session:
        actor = User(
            email="generator@example.invalid",
            full_name="Người giả T25",
            role=UserRole.admin,
            password_hash="synthetic-unused-hash",
        )
        session.add(actor)
        session.flush()
        records = seed_records(session, actor)
        records.application.owner_id = actor.id
        records.application.stage = "screening"
        records.application.stage_entered_at = now - timedelta(days=4)
        session.commit()
    barrier = Barrier(2)

    def run():
        with Session(empty_engine) as session:
            barrier.wait(timeout=10)
            return reminders.generate(session, now)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: run(), range(2)))
    assert sorted(results) == [0, 1]
    with Session(empty_engine) as session:
        assert session.scalar(select(func.count()).select_from(Task)) == 1
