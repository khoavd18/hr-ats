from typing import Annotated, cast

from fastapi import APIRouter, Depends
from redis import Redis
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, current_user
from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.errors import ErrorResponse
from app.core.permissions import authorize
from app.core.redis import get_redis
from app.email.inbound import STATUS_KEY
from app.schemas.system import HealthResponse, MailboxStatus, PublicConfigResponse
from app.services.pipeline import stage_labels
from app.services.system import check_dependencies

router = APIRouter()


@router.get("/health", response_model=HealthResponse, responses={503: {"model": ErrorResponse}})
def health(
    session: Annotated[Session, Depends(get_session)],
    redis_client: Annotated[Redis, Depends(get_redis)],
) -> HealthResponse:
    check_dependencies(session, redis_client)
    return HealthResponse()


@router.get(
    "/config/public", response_model=PublicConfigResponse, dependencies=[Depends(current_user)]
)
def public_config(settings: Annotated[Settings, Depends(get_settings)]) -> PublicConfigResponse:
    return PublicConfigResponse(
        hiring_unit_label=settings.hiring_unit_label,
        stages=stage_labels(settings.hiring_unit_label),
    )


@router.get("/settings/mailbox", response_model=MailboxStatus)
def mailbox_status(
    actor: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
    redis_client: Annotated[Redis, Depends(get_redis)],
) -> MailboxStatus:
    authorize(actor, "mailbox.view")
    try:
        data = cast(dict[str, str], redis_client.hgetall(STATUS_KEY))
        return MailboxStatus.model_validate(
            {
                "enabled": settings.imap_enabled,
                "last_read_at": data.get("last_read_at"),
                "last_error": data.get("last_error") or None,
            }
        )
    except Exception:
        return MailboxStatus(enabled=settings.imap_enabled, last_error="IMAP_STATUS_UNAVAILABLE")
