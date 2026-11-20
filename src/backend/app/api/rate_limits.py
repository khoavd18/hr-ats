from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from redis import Redis

from app.api.dependencies import CSRF, Config, CurrentUser
from app.core.rate_limit import check_limit
from app.core.redis import get_redis


def get_limit_redis(settings: Config) -> Iterator[Redis]:
    yield from get_redis(settings)


LimitRedis = Annotated[Redis, Depends(get_limit_redis)]


def limit_login(request: Request, settings: Config, redis: LimitRedis, csrf: CSRF) -> None:
    # Uvicorn handles forwarding only from explicitly trusted proxies. Never read XFF here.
    peer = request.client.host if request.client else "unknown"
    check_limit(redis, settings, "login", peer, settings.login_rate_limit_per_minute)


def limit_upload(actor: CurrentUser, settings: Config, redis: LimitRedis) -> None:
    check_limit(redis, settings, "upload", str(actor.id), settings.upload_rate_limit_per_minute)
