import hmac
import re
from datetime import date, datetime
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.logging import redact
from app.models.enums import AiLevel, ApplicationStage
from app.models.integrations import WEBHOOK_PATH_PATTERN, IntegrationEvent, WebhookEndpoint

WEBHOOK_PATH = re.compile(WEBHOOK_PATH_PATTERN, re.ASCII)
SIGNATURE_WINDOW_SECONDS = 300
IntegrationKind = Literal["cv-scored", "pipeline", "overdue", "daily-report"]
PATHS: dict[IntegrationKind, str] = {
    "cv-scored": "/webhook/hr-ats/cv-scored",
    "pipeline": "/webhook/hr-ats/pipeline",
    "overdue": "/webhook/hr-ats/overdue",
    "daily-report": "/webhook/hr-ats/daily-report",
}
Payload = dict[str, int | str]
EVENT_KINDS: dict[str, IntegrationKind] = {
    "cv.scored": "cv-scored",
    "application.stage_changed": "pipeline",
    "interview.scheduled": "pipeline",
    "interview.cancelled": "pipeline",
    "task.overdue": "overdue",
    "report.daily_ready": "daily-report",
}


def is_count(value: int | str | None, *, minimum: int = 0) -> bool:
    return type(value) is int and minimum <= value <= 2**53 - 1


def is_reference(value: int | str | None) -> bool:
    return (
        isinstance(value, str)
        and re.fullmatch(r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}", value)
        is not None
    )


def is_report_date(value: int | str | None) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def validate_payload(event_type: str, payload: Payload) -> None:
    application = payload.get("application_id")
    if event_type == "integration.test":
        valid = not payload
    elif event_type in {"task.overdue_summary", "task.overdue"}:
        valid = set(payload) == {"overdue_count"} and is_count(
            payload.get("overdue_count"), minimum=1
        )
    elif event_type == "cv.scored":
        valid = (
            set(payload) == {"application_id", "ai_level"}
            and is_reference(application)
            and payload["ai_level"] in set(AiLevel)
        )
    elif event_type == "application.stage_changed":
        valid = (
            set(payload) == {"application_id", "stage"}
            and is_reference(application)
            and payload["stage"] in set(ApplicationStage)
        )
    elif event_type in {"interview.scheduled", "interview.cancelled"}:
        scheduled = payload.get("scheduled_epoch")
        valid = (
            set(payload) == {"application_id", "scheduled_epoch"}
            and is_reference(application)
            and type(scheduled) is int
            and -62135596800 <= scheduled <= 253402300799
        )
    elif event_type == "report.daily_ready":
        counts = {"new_cvs", "interviews", "placements"}
        valid = (
            set(payload) == counts | {"report_date"}
            and is_report_date(payload.get("report_date"))
            and all(is_count(payload.get(key)) for key in counts)
        )
    else:
        valid = False
    metadata = {key: value for key, value in payload.items() if key != "application_id"}
    if not valid or redact(metadata) != metadata:
        raise ValueError("Invalid integration event metadata")


def queue_notification(
    session: Session,
    event_type: str,
    dedupe_key: UUID,
    payload: Payload,
    now: datetime,
    *,
    expires_at: datetime | None = None,
) -> UUID | None:
    endpoint_id = session.scalar(
        select(WebhookEndpoint.id).where(
            WebhookEndpoint.path == PATHS[EVENT_KINDS[event_type]],
            WebhookEndpoint.enabled.is_(True),
        )
    )
    if endpoint_id is None:
        return None
    return enqueue_integration_event(
        session,
        endpoint_id=endpoint_id,
        event_type=event_type,
        dedupe_key=dedupe_key,
        payload=payload,
        now=now,
        expires_at=expires_at,
    )


def enqueue_integration_event(
    session: Session,
    *,
    endpoint_id: UUID,
    event_type: str,
    dedupe_key: UUID,
    payload: Payload,
    now: datetime,
    expires_at: datetime | None = None,
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
            expires_at=expires_at,
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
