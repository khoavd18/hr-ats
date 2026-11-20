"""The private overdue-task summary uses the existing 'Việc của tôi' scope."""

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import OverdueWebhookEvent, Task, User
from app.services.tasks import OPEN, VIETNAM, visible_tasks
from app.workers.celery_app import celery_app
from app.workers.tasks import worker_session

logger = logging.getLogger(__name__)
RETRY_DELAYS = (60, 300, 900)


def queue_summary(session: Session, user_id: UUID, now: datetime) -> None:
    actor = session.get(User, user_id)
    if actor is None or not actor.is_active:
        return
    overdue = visible_tasks(actor).where(Task.status.in_(OPEN), Task.due_at < now)
    count = session.scalar(select(func.count()).select_from(overdue.subquery()))
    if not count:
        return
    session.execute(
        insert(OverdueWebhookEvent)
        .values(
            id=uuid4(),
            user_id=user_id,
            reminder_day=now.astimezone(VIETNAM).date(),
            overdue_count=count,
            next_attempt_at=now,
        )
        .on_conflict_do_nothing(index_elements=["user_id", "reminder_day"])
    )
    session.commit()


def send_summary(settings: Settings, event: OverdueWebhookEvent) -> bool:
    event_id = str(event.id)
    try:
        response = httpx.post(
            settings.n8n_overdue_webhook_url,
            headers={"X-HR-ATS-Key": settings.n8n_overdue_webhook_key.get_secret_value()},
            json={
                "event_id": event_id,
                "event_type": "task.overdue_summary",
                "version": 1,
                "overdue_count": event.overdue_count,
            },
            timeout=5.0,
            follow_redirects=False,
            trust_env=False,
        )
        if not response.is_success:
            return False
        reply = response.json()
    except (httpx.HTTPError, ValueError):
        return False
    return (
        isinstance(reply, dict)
        and reply.get("received") is True
        and reply.get("event_id") == event_id
    )


def deliver_summary(session: Session, settings: Settings, now: datetime) -> None:
    reminder_day = now.astimezone(VIETNAM).date()
    # Lock only the delivery row for this short HTTP attempt, allowing another
    # worker to skip it and leaving the scheduling and HR transactions independent.
    event = session.scalar(
        select(OverdueWebhookEvent)
        .join(User, User.id == OverdueWebhookEvent.user_id)
        .where(
            User.is_active.is_(True),
            OverdueWebhookEvent.user_id == settings.n8n_overdue_user_id,
            OverdueWebhookEvent.reminder_day == reminder_day,
            OverdueWebhookEvent.delivered_at.is_(None),
            OverdueWebhookEvent.next_attempt_at <= now,
        )
        .with_for_update(of=OverdueWebhookEvent, skip_locked=True)
    )
    if event is None:
        return
    event.attempts += 1
    if send_summary(settings, event):
        event.delivered_at = now
    else:
        delay = RETRY_DELAYS[min(event.attempts, len(RETRY_DELAYS)) - 1]
        event.next_attempt_at = now + timedelta(seconds=delay)
        logger.warning("Overdue webhook attempt failed for event %s", event.id)
    session.commit()


@celery_app.task(name="queue_overdue_webhook")
def queue_overdue_webhook() -> None:
    settings = get_settings()
    if settings.n8n_overdue_enabled and settings.n8n_overdue_user_id is not None:
        with worker_session() as session:
            queue_summary(session, settings.n8n_overdue_user_id, datetime.now(UTC))


@celery_app.task(name="deliver_overdue_webhook")
def deliver_overdue_webhook() -> None:
    settings = get_settings()
    if settings.n8n_overdue_enabled:
        with worker_session() as session:
            deliver_summary(session, settings, datetime.now(UTC))
