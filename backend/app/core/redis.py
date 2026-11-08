from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from redis import Redis

from app.core.config import Settings, get_settings


def get_redis(settings: Annotated[Settings, Depends(get_settings)]) -> Iterator[Redis]:
    with Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    ) as client:
        yield client
