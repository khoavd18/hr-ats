"""The private overdue-task summary uses the existing 'Việc của tôi' scope."""

import logging
from datetime import UTC, datetime, time, timedelta
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import httpx
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import IntegrationEvent, OverdueWebhookEvent, Task, User
from app.services.integration_events import queue_notification
from app.services.tasks import OPEN, VIETNAM, visible_tasks
from app.workers.celery_app import celery_app
from app.workers.tasks import worker_session

logger = logging.getLogger(__name__)
RETRY_DELAYS = (60, 300, 900)


def queue_summary(session: Session, user_id: UUID, now: datetime, *, signed: bool = False) -> None:
    actor = session.get(User, user_id)
    if actor is None or not actor.is_active:
        return
    session.execute(select(func.pg_advisory_xact_lock(340039)))
    day = now.astimezone(VIETNAM).date()
    key = uuid5(NAMESPACE_URL, f"hr-ats:task.overdue:{user_id}:{day.isoformat()}")
    if (
        signed
        and session.scalar(
            select(OverdueWebhookEvent.id).where(
                OverdueWebhookEvent.user_id == user_id, OverdueWebhookEvent.reminder_day == day
            )
        )
        is not None
    ):
        return
    if (
        not signed
        and session.scalar(
            select(IntegrationEvent.id).where(
                IntegrationEvent.event_type == "task.overdue", IntegrationEvent.dedupe_key == key
            )
        )
        is not None
    ):
        return
    overdue = visible_tasks(actor).where(Task.status.in_(OPEN), Task.due_at < now)
    count = session.scalar(select(func.count()).select_from(overdue.subquery()))
    if not count:
        return
    if signed:
        queue_notification(
            session,
            "task.overdue",
            key,
            {"overdue_count": count},
            now,
            expires_at=datetime.combine(day + timedelta(days=1), time.min, tzinfo=VIETNAM),
        )
        session.commit()
        return
    session.execute(
        insert(OverdueWebhookEvent)
        .values(
            id=uuid4(),
            user_id=user_id,
            reminder_day=day,
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
    if (
        settings.n8n_overdue_enabled or settings.integration_webhooks_enabled
    ) and settings.n8n_overdue_user_id is not None:
        with worker_session() as session:
            queue_summary(
                session,
                settings.n8n_overdue_user_id,
                datetime.now(UTC),
                signed=settings.integration_webhooks_enabled,
            )


@celery_app.task(name="deliver_overdue_webhook")
def deliver_overdue_webhook() -> None:
    settings = get_settings()
    if settings.n8n_overdue_enabled and not settings.integration_webhooks_enabled:
        with worker_session() as session:
            deliver_summary(session, settings, datetime.now(UTC))
