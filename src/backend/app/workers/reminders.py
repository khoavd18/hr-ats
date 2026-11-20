"""Fixed task rules and daily internal mail. Celery payloads contain IDs only."""

from datetime import UTC, datetime, timedelta
from html import escape
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Activity, Application, EmailMessage, Interview, Task, User
from app.models.enums import ApplicationStage, EmailStatus
from app.services.ranking import visible_applications
from app.services.tasks import CONTACT, OPEN, RESULT, VIETNAM, due_tasks, job_scope
from app.workers.celery_app import celery_app
from app.workers.tasks import worker_session


def generate(session: Session, now: datetime) -> int:
    session.execute(select(func.pg_advisory_xact_lock(250025)))
    recent_activity = exists().where(
        Activity.application_id == Application.id,
        Activity.deleted_at.is_(None),
        Activity.occurred_at >= now - timedelta(days=3),
    )
    stale_interview = exists().where(
        Interview.application_id == Application.id,
        Interview.deleted_at.is_(None),
        Interview.result == "pending",
        Interview.scheduled_at + Interview.duration_minutes * timedelta(minutes=1)
        < now - timedelta(days=1),
    )
    rules = (
        (
            CONTACT,
            (Application.stage == ApplicationStage.screening)
            & (Application.stage_entered_at < now - timedelta(days=3))
            & ~recent_activity,
        ),
        (
            RESULT,
            stale_interview
            & Application.stage.in_(
                [
                    ApplicationStage.new,
                    ApplicationStage.screening,
                    ApplicationStage.submitted,
                    ApplicationStage.interview,
                    ApplicationStage.offer,
                ]
            ),
        ),
    )
    count = 0
    for title, condition in rules:
        query = visible_applications().where(
            condition,
            ~exists().where(
                Task.application_id == Application.id,
                Task.title == title,
                Task.status.in_(OPEN),
                Task.deleted_at.is_(None),
            ),
        )
        for application in session.scalars(query).all():
            owner = session.get(User, application.owner_id)
            if owner is None or not owner.is_active:
                continue
            if not session.scalar(
                select(
                    exists().where(
                        Application.job_id.in_(job_scope(owner)), Application.id == application.id
                    )
                )
            ):
                continue
            session.add(
                Task(
                    title=title,
                    assignee_id=owner.id,
                    created_by=owner.id,
                    application_id=application.id,
                    job_id=application.job_id,
                    due_at=now,
                )
            )
            count += 1
    session.commit()
    return count


@celery_app.task(name="generate_followup_tasks")
def generate_followup_tasks() -> None:
    with worker_session() as session:
        generate(session, datetime.now(UTC))


def reminder_id(user_id: UUID, day) -> UUID:
    # Stable daily identity, encoded as v4 to match the application's metadata
    # UUID allowlist. This is a deduplication key, never an authorization token.
    digest = uuid5(NAMESPACE_URL, f"hr-ats/task-reminder/{day.isoformat()}/{user_id}")
    return UUID(bytes=digest.bytes, version=4)


def is_reminder(row: EmailMessage) -> bool:
    # API clients cannot supply IDs, message IDs, or created_at. Only this producer
    # creates this marker; null application_id alone never grants automatic send.
    day = row.created_at.astimezone(VIETNAM).date()
    expected = reminder_id(row.created_by, day)
    return (
        row.id == expected
        and row.message_id == f"<{expected}.task-reminder@hr-ats.invalid>"
        and row.application_id is None
        and row.template_id is None
    )


def reminder_html(session: Session, actor: User, now: datetime) -> str:
    rows = due_tasks(session, actor, now)
    if not rows:
        raise AppError("NOT_FOUND", "Không còn việc đến hạn.", 404)
    # No CV/contact data is fetched. Escape HR-entered text before HTML generation.
    return (
        "<p>Các việc đến hạn và quá hạn của bạn:</p><ul>"
        + "".join(
            f"<li>{escape(row.title or '')} — {row.due_at.astimezone(VIETNAM):%d/%m/%Y %H:%M}</li>"
            for row in rows
            if row.due_at is not None
        )
        + "</ul><p>Mở mục Việc của tôi trong hệ thống tuyển dụng để cập nhật.</p>"
    )


def lock_reminder_snapshots(session: Session) -> None:
    # Both the producer and purge acquire this before reading tasks or taking
    # child-row locks, and retain it through the snapshot/erasure commit.
    session.execute(select(func.pg_advisory_xact_lock(250026)))


def queue_reminders(session: Session, now: datetime) -> list:
    lock_reminder_snapshots(session)
    # Read eligibility after waiting: a completed freeze/purge hides these tasks.
    day = now.astimezone(VIETNAM).date()
    messages = []
    for actor in session.scalars(select(User).where(User.is_active.is_(True)).order_by(User.id)):
        try:
            body = reminder_html(session, actor, now)
        except AppError:
            continue
        record_id = reminder_id(actor.id, day)
        row = session.get(EmailMessage, record_id)
        if row is None:
            row = EmailMessage(
                id=record_id,
                created_at=now,
                created_by=actor.id,
                to_email=actor.email,
                subject="Nhắc việc đến hạn",
                body_html=body,
                message_id=f"<{record_id}.task-reminder@hr-ats.invalid>",
                status=EmailStatus.queued,
                scheduled_for=now,
            )
            session.add(row)
        # Recover committed-but-unpublished messages on the next run. Failed
        # deliveries are retried by the existing SMTP worker with its checkpoints.
        if row.status == EmailStatus.queued and row.scheduled_for:
            messages.append((str(row.id), row.message_id, row.scheduled_for.isoformat()))
    session.commit()
    return messages


@celery_app.task(name="remind_due_tasks")
def remind_due_tasks() -> None:
    from app.workers.email import send_email_message

    with worker_session() as session:
        messages = queue_reminders(session, datetime.now(UTC))
    for args in messages:
        try:
            send_email_message.apply_async(args=list(args))
        except Exception:
            # Persisted queued messages are recovered by the next producer run;
            # never log broker exceptions that may contain credentials.
            continue
