from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select

from app.models import AuditLog, IntegrationEvent, OverdueWebhookEvent, Task, WebhookEndpoint
from app.models.enums import ApplicationStage, ProcessingStatus
from app.reports.scheduled import queue_reports
from app.schemas.recruitment import InterviewCreate
from app.services.integration_events import PATHS
from app.services.pipeline import move
from app.services.recruitment import cancel_interview, create_interview, records
from app.workers import tasks
from app.workers.integration_webhooks import deliver_next
from app.workers.overdue_webhook import queue_summary
from tests.api.test_integration_webhooks import configured
from tests.api.test_pipeline import seed_records


def enable(session, kind):
    session.add(WebhookEndpoint(id=uuid4(), path=PATHS[kind], enabled=True))
    session.commit()


def test_stage_interview_and_cancel_events_only_include_selected_metadata(db_session, account):
    data = seed_records(db_session, account)
    data.application.stage = ApplicationStage.submitted
    db_session.commit()
    enable(db_session, "pipeline")
    interview = create_interview(
        db_session,
        account,
        data.application.id,
        InterviewCreate(
            scheduled_at=datetime(2026, 11, 27, 5, tzinfo=UTC),
            location_or_link="Địa điểm giả",
            interviewers=["Người phỏng vấn giả"],
        ),
    )
    cancel_interview(db_session, account, interview.id)
    assert records(db_session, data.application.id).interviews == []
    assert data.application.stage == ApplicationStage.interview
    events = {row.event_type: row.payload for row in db_session.scalars(select(IntegrationEvent))}
    assert events == {
        "application.stage_changed": {
            "application_id": str(data.application.id),
            "stage": "interview",
        },
        "interview.scheduled": {
            "application_id": str(data.application.id),
            "scheduled_epoch": 1795755600,
        },
        "interview.cancelled": {
            "application_id": str(data.application.id),
            "scheduled_epoch": 1795755600,
        },
    }
    assert (
        db_session.scalar(
            select(AuditLog).where(AuditLog.action == "interview.cancelled")
        ).entity_id
        == interview.id
    )


def test_outbox_rolls_back_with_the_actual_stage_change(db_session, account):
    data = seed_records(db_session, account)
    enable(db_session, "pipeline")
    application_id = data.application.id
    move(db_session, account, application_id, ApplicationStage.screening, commit=False)
    assert db_session.scalar(select(IntegrationEvent)).payload["stage"] == "screening"
    db_session.rollback()
    assert db_session.scalar(select(IntegrationEvent)) is None
    assert data.application.stage == ApplicationStage.new


def test_scoring_worker_publishes_level_without_cv_and_is_idempotent(
    db_session, account, monkeypatch
):
    data = seed_records(db_session, account)
    data.candidate.anonymized_text = "Kinh nghiệm Python và SQL. " * 30
    data.job.must_have = ["Python"]
    data.application.ai_status = ProcessingStatus.pending
    enable(db_session, "cv-scored")

    @contextmanager
    def worker_session():
        yield db_session

    monkeypatch.setattr(tasks, "worker_session", worker_session)
    tasks.score_application(str(data.application.id))
    tasks.score_application(str(data.application.id))
    event = db_session.scalars(select(IntegrationEvent)).one()
    assert event.event_type == "cv.scored"
    assert event.payload == {
        "application_id": str(data.application.id),
        "ai_level": data.application.ai_level,
    }


def test_overdue_signed_alert_cannot_duplicate_legacy_or_cross_midnight(db_session, account):
    enable(db_session, "overdue")
    now = datetime(2026, 11, 25, 16, 55, tzinfo=UTC)
    db_session.add(
        Task(
            title="Việc giả",
            assignee_id=account.id,
            created_by=account.id,
            due_at=now - timedelta(minutes=1),
        )
    )
    db_session.commit()
    queue_summary(db_session, account.id, now, signed=True)
    queue_summary(db_session, account.id, now, signed=True)
    queue_summary(db_session, account.id, now)
    assert db_session.scalar(select(OverdueWebhookEvent)) is None
    event = db_session.scalars(select(IntegrationEvent)).one()
    assert event.event_type == "task.overdue"
    assert event.payload == {"overdue_count": 1}
    assert event.expires_at == now + timedelta(minutes=5)
    assert not deliver_next(db_session, configured(), event.expires_at)


def test_daily_report_emits_one_aggregate_snapshot_for_vietnam_date(db_session, account):
    enable(db_session, "daily-report")
    now = datetime(2026, 11, 24, 22, 0, tzinfo=UTC)
    mail = queue_reports(db_session, "daily", now, configured())
    assert len(mail) == 1
    assert queue_reports(db_session, "daily", now + timedelta(minutes=5), configured()) == mail
    queue_reports(db_session, "weekly", now, configured())
    event = db_session.scalars(select(IntegrationEvent)).one()
    assert event.event_type == "report.daily_ready"
    assert event.payload == {
        "report_date": "2026-11-25",
        "new_cvs": 0,
        "interviews": 0,
        "placements": 0,
    }
