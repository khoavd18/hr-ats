"""Shared fixed-window limits; Redis holds only short-lived HMAC identifiers."""

import hashlib
import hmac
from typing import cast

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import Settings
from app.core.errors import AppError

KEY_PREFIX = "hr-ats:rate:"
WINDOW_SECONDS = 60
SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
local ttl = redis.call('TTL', KEYS[1])
return {count, ttl}
"""


def check_limit(client: Redis, settings: Settings, action: str, subject: str, limit: int) -> None:
    digest = hmac.new(
        settings.secret_key.get_secret_value().encode(),
        f"rate:{action}:{subject}".encode(),
        hashlib.sha256,
    ).hexdigest()
    try:
        count, ttl = cast(
            list[int], client.eval(SCRIPT, 1, KEY_PREFIX + action + ":" + digest, WINDOW_SECONDS)
        )
    except RedisError:
        raise AppError("SERVICE_UNAVAILABLE", "Dịch vụ tạm thời không khả dụng.", 503) from None
    if count > limit:
        raise AppError(
            "RATE_LIMITED",
            "Bạn thao tác quá nhanh. Vui lòng thử lại sau.",
            429,
            headers={"Retry-After": str(max(1, ttl)), "Cache-Control": "no-store"},
        )
