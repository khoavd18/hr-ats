from collections.abc import Iterator

from redis import Redis

from app.core.config import get_settings


def get_redis() -> Iterator[Redis]:
    with Redis.from_url(
        get_settings().redis_url,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    ) as client:
        yield client
