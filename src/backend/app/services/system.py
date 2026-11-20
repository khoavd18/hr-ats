import logging

from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.errors import AppError

logger = logging.getLogger(__name__)


def check_dependencies(session: Session, redis_client: Redis) -> None:
    available = True
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        available = False
        logger.warning("Health dependency unavailable", extra={"dependency": "db"})
    try:
        if not redis_client.ping():
            available = False
            logger.warning("Health dependency unavailable", extra={"dependency": "redis"})
    except RedisError:
        available = False
        logger.warning("Health dependency unavailable", extra={"dependency": "redis"})
    if not available:
        raise AppError("SERVICE_UNAVAILABLE", "Dịch vụ tạm thời không khả dụng.", 503)
