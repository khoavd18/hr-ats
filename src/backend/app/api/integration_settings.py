import logging
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Response
from kombu.exceptions import OperationalError
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.api.dependencies import DB, Config, CurrentUser
from app.core.errors import AppError
from app.models import IntegrationEvent, WebhookEndpoint
from app.models.users import User, UserRole
from app.schemas.users import InputModel
from app.services.audit import record_audit
from app.services.integration_events import PATHS, IntegrationKind, enqueue_integration_event
from app.workers.integration_webhooks import deliver_integration_webhooks

router = APIRouter(prefix="/settings/integrations", tags=["integrations"])
logger = logging.getLogger(__name__)

DeliveryStatus = Literal["sent", "failed", "paused", "retrying", "pending"]
KINDS = {path: kind for kind, path in PATHS.items()}


class IntegrationToggle(InputModel):
    enabled: bool


class NotificationStatus(BaseModel):
    kind: IntegrationKind
    enabled: bool


class DeliveryHistory(BaseModel):
    id: UUID
    kind: IntegrationKind
    is_test: bool
    created_at: datetime
    status: DeliveryStatus
    error_code: Literal["WEBHOOK_DELIVERY_FAILED"] | None


class IntegrationStatus(BaseModel):
    available: bool
    notifications: list[NotificationStatus]
    history: list[DeliveryHistory]


def check_admin(actor: User, response: Response) -> None:
    if actor.role != UserRole.admin:
        raise AppError("FORBIDDEN", "Chỉ quản trị viên được quản lý tích hợp.", 403)
    response.headers["Cache-Control"] = "no-store"


def delivery_status(event: IntegrationEvent, enabled: bool) -> DeliveryStatus:
    if event.delivered_at is not None:
        return "sent"
    if event.failed_at is not None:
        return "failed"
    if not enabled:
        return "paused"
    return "retrying" if event.attempts else "pending"


@router.get("", response_model=IntegrationStatus)
def get_settings(response: Response, session: DB, actor: CurrentUser, config: Config):
    check_admin(actor, response)
    endpoints = {
        path: enabled
        for path, enabled in session.execute(
            select(WebhookEndpoint.path, WebhookEndpoint.enabled).where(
                WebhookEndpoint.path.in_(PATHS.values())
            )
        )
    }
    deliveries = session.execute(
        select(IntegrationEvent, WebhookEndpoint.path)
        .join(WebhookEndpoint)
        .where(WebhookEndpoint.path.in_(PATHS.values()))
        .order_by(IntegrationEvent.created_at.desc(), IntegrationEvent.id.desc())
        .limit(50)
    )
    return {
        "available": config.integration_webhooks_enabled,
        "notifications": [
            {"kind": kind, "enabled": endpoints.get(path, False)} for kind, path in PATHS.items()
        ],
        "history": [
            {
                "id": event.id,
                "kind": KINDS[path],
                "is_test": event.event_type == "integration.test",
                "created_at": event.created_at,
                "status": delivery_status(
                    event, config.integration_webhooks_enabled and endpoints[path]
                ),
                "error_code": (
                    "WEBHOOK_DELIVERY_FAILED"
                    if event.attempts and event.delivered_at is None
                    else None
                ),
            }
            for event, path in deliveries
        ],
    }


@router.put("/{kind}", response_model=NotificationStatus)
def toggle(
    kind: IntegrationKind,
    body: IntegrationToggle,
    response: Response,
    session: DB,
    actor: CurrentUser,
):
    check_admin(actor, response)
    statement = insert(WebhookEndpoint).values(id=uuid4(), path=PATHS[kind], enabled=body.enabled)
    endpoint_id = session.execute(
        statement.on_conflict_do_update(
            constraint="uq_webhook_endpoint_path",
            set_={"enabled": statement.excluded.enabled},
        ).returning(WebhookEndpoint.id)
    ).scalar_one()
    record_audit(
        session,
        actor_id=actor.id,
        action="integration.endpoint_updated",
        entity="webhook_endpoint",
        entity_id=endpoint_id,
        details={"kind": kind, "enabled": body.enabled},
    )
    session.commit()
    return {"kind": kind, "enabled": body.enabled}


@router.post("/{kind}/test", status_code=202)
def send_test(
    kind: IntegrationKind, response: Response, session: DB, actor: CurrentUser, config: Config
) -> dict[str, UUID]:
    check_admin(actor, response)
    endpoint_id = session.scalar(
        select(WebhookEndpoint.id).where(
            WebhookEndpoint.path == PATHS[kind], WebhookEndpoint.enabled.is_(True)
        )
    )
    if not config.integration_webhooks_enabled or endpoint_id is None:
        raise AppError("INTEGRATION_DISABLED", "Hãy bật thông báo trước khi gửi thử.", 409)
    event_id = enqueue_integration_event(
        session,
        endpoint_id=endpoint_id,
        event_type="integration.test",
        dedupe_key=uuid4(),
        payload={},
        now=datetime.now(UTC),
    )
    if event_id is None:
        raise AppError("INTEGRATION_DISABLED", "Hãy bật thông báo trước khi gửi thử.", 409)
    record_audit(
        session,
        actor_id=actor.id,
        action="integration.test_requested",
        entity="integration_event",
        entity_id=event_id,
        details={"kind": kind},
    )
    session.commit()
    try:
        deliver_integration_webhooks.delay()
    except OperationalError:
        # The event is committed. Beat can recover without a second submission.
        logger.warning("Unable to wake the integration delivery worker")
    return {"event_id": event_id}
