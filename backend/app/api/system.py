from typing import Annotated

from fastapi import APIRouter, Depends
from redis import Redis
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.errors import ErrorResponse
from app.core.redis import get_redis
from app.schemas.system import HealthResponse, PublicConfigResponse
from app.services.system import check_dependencies

router = APIRouter()


@router.get("/health", response_model=HealthResponse, responses={503: {"model": ErrorResponse}})
def health(
    session: Annotated[Session, Depends(get_session)],
    redis_client: Annotated[Redis, Depends(get_redis)],
) -> HealthResponse:
    check_dependencies(session, redis_client)
    return HealthResponse()


@router.get("/config/public", response_model=PublicConfigResponse)
def public_config(settings: Annotated[Settings, Depends(get_settings)]) -> PublicConfigResponse:
    return PublicConfigResponse(hiring_unit_label=settings.hiring_unit_label)
