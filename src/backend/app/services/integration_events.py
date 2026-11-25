import hmac
import re
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.logging import redact
from app.models.integrations import WEBHOOK_PATH_PATTERN, IntegrationEvent, WebhookEndpoint

WEBHOOK_PATH = re.compile(WEBHOOK_PATH_PATTERN, re.ASCII)
SIGNATURE_WINDOW_SECONDS = 300


def validate_payload(event_type: str, payload: dict[str, int]) -> None:
    if event_type == "integration.test":
        valid = not payload
    elif event_type == "task.overdue_summary":
        count = payload.get("overdue_count")
        valid = set(payload) == {"overdue_count"} and type(count) is int and 0 < count <= 2**53 - 1
    else:
        valid = False
    if not valid or redact(payload) != payload:
        raise ValueError("Invalid integration event metadata")


def enqueue_integration_event(
    session: Session,
    *,
    endpoint_id: UUID,
    event_type: str,
    dedupe_key: UUID,
    payload: dict[str, int],
    now: datetime,
) -> UUID | None:
    """Write within the producer's transaction. A retry returns the existing delivery ID."""
    validate_payload(event_type, payload)
    endpoint = session.get(WebhookEndpoint, endpoint_id)
    if endpoint is None or not endpoint.enabled:
        return None
    event_id = session.scalar(
        insert(IntegrationEvent)
        .values(
            id=uuid4(),
            endpoint_id=endpoint_id,
            event_type=event_type,
            dedupe_key=dedupe_key,
            payload=payload,
            created_at=now,
            next_attempt_at=now,
        )
        .on_conflict_do_nothing(constraint="uq_integration_event_delivery")
        .returning(IntegrationEvent.id)
    )
    if event_id is not None:
        return event_id
    return session.execute(
        select(IntegrationEvent.id).where(
            IntegrationEvent.endpoint_id == endpoint_id,
            IntegrationEvent.event_type == event_type,
            IntegrationEvent.dedupe_key == dedupe_key,
        )
    ).scalar_one()


def webhook_signature(secret: str, timestamp: str, path: str, body: bytes) -> str:
    message = f"{timestamp}.{path}.".encode("ascii") + body
    return "v1=" + hmac.digest(secret.encode("utf-8"), message, "sha256").hex()


def verify_webhook_signature(
    secret: str, timestamp: str, path: str, body: bytes, signature: str, now: datetime
) -> bool:
    if (
        not re.fullmatch(r"[0-9]{1,12}", timestamp)
        or not re.fullmatch(r"v1=[0-9a-f]{64}", signature)
        or not WEBHOOK_PATH.fullmatch(path)
        or abs(int(now.timestamp()) - int(timestamp)) > SIGNATURE_WINDOW_SECONDS
    ):
        return False
    return hmac.compare_digest(signature, webhook_signature(secret, timestamp, path, body))
