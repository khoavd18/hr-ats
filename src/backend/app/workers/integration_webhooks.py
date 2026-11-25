import json
import logging
from datetime import UTC, datetime, timedelta
from time import monotonic

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import IntegrationEvent, WebhookEndpoint
from app.services.integration_events import WEBHOOK_PATH, validate_payload, webhook_signature
from app.workers.celery_app import celery_app
from app.workers.tasks import worker_session

logger = logging.getLogger(__name__)
RETRY_DELAYS = (60, 300, 900)
MAX_ACK_BYTES = 1024
HTTP_TIMEOUT = 5.0


def send_event(settings: Settings, path: str, event: IntegrationEvent, now: datetime) -> bool:
    if not WEBHOOK_PATH.fullmatch(path):
        return False
    event_id = str(event.id)
    timestamp = str(int(now.timestamp()))
    try:
        validate_payload(event.event_type, event.payload)
        body = json.dumps(
            {
                "event_id": event_id,
                "event_type": event.event_type,
                "version": 1,
                "data": event.payload,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        deadline = monotonic() + HTTP_TIMEOUT
        with httpx.stream(
            "POST",
            settings.integration_webhook_origin + path,
            content=body,
            headers={
                "Content-Type": "application/json",
                "Accept-Encoding": "identity",
                "X-HR-ATS-Timestamp": timestamp,
                "X-HR-ATS-Signature": webhook_signature(
                    settings.integration_webhook_secret.get_secret_value(), timestamp, path, body
                ),
            },
            timeout=HTTP_TIMEOUT,
            follow_redirects=False,
            trust_env=False,
        ) as response:
            if not response.is_success:
                return False
            ack = bytearray()
            for chunk in response.iter_raw():
                if len(ack) + len(chunk) > MAX_ACK_BYTES or monotonic() > deadline:
                    return False
                ack.extend(chunk)
        reply = json.loads(ack)
    except (httpx.HTTPError, ValueError, RecursionError):
        return False
    return (
        isinstance(reply, dict)
        and reply.get("received") is True
        and reply.get("event_id") == event_id
    )


def deliver_next(session: Session, settings: Settings, now: datetime) -> bool:
    delivery = session.execute(
        select(IntegrationEvent, WebhookEndpoint.path)
        .join(WebhookEndpoint)
        .where(
            WebhookEndpoint.enabled.is_(True),
            IntegrationEvent.delivered_at.is_(None),
            IntegrationEvent.failed_at.is_(None),
            IntegrationEvent.next_attempt_at <= now,
        )
        .order_by(IntegrationEvent.next_attempt_at, IntegrationEvent.id)
        .limit(1)
        .with_for_update(of=IntegrationEvent, skip_locked=True)
    ).one_or_none()
    if delivery is None:
        return False
    event, path = delivery
    event.attempts += 1
    if send_event(settings, path, event, now):
        event.delivered_at = now
    else:
        if event.attempts <= len(RETRY_DELAYS):
            event.next_attempt_at = now + timedelta(seconds=RETRY_DELAYS[event.attempts - 1])
        else:
            event.failed_at = now
        logger.warning("Integration webhook delivery failed for event %s", event.id)
    session.commit()
    return True


@celery_app.task(name="deliver_integration_webhooks")
def deliver_integration_webhooks() -> None:
    settings = get_settings()
    if settings.integration_webhooks_enabled:
        with worker_session() as session:
            for _ in range(10):
                if not deliver_next(session, settings, datetime.now(UTC)):
                    break
