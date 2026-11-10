"""Exercise the production Lua script across real Redis clients, no sleeping."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from redis import Redis

from app.core import rate_limit
from app.core.config import get_settings
from app.core.errors import AppError


def test_shared_limit_is_atomic_expiring_and_hides_subject():
    settings = get_settings()
    subject = "synthetic-rate@example.invalid"

    def attempt(_):
        with Redis.from_url(settings.redis_url) as client:
            try:
                rate_limit.check_limit(client, settings, "login", subject, 5)
                return 200
            except AppError as error:
                return error.status

    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(attempt, range(12)))
    assert statuses.count(200) == 5 and statuses.count(429) == 7
    with Redis.from_url(settings.redis_url, decode_responses=True) as client:
        keys = list(client.scan_iter(rate_limit.KEY_PREFIX + "*"))
        assert len(keys) == 1 and subject not in keys[0]
        ttl = client.ttl(keys[0])
        assert 1 <= ttl <= 60
        with pytest.raises(AppError):
            rate_limit.check_limit(client, settings, "login", subject, 5)
        assert 1 <= client.ttl(keys[0]) <= ttl  # Rejection does not renew the window.
        client.expire(keys[0], 0)  # Only this test's UUID namespace.
        rate_limit.check_limit(client, settings, "login", subject, 5)
        # Independent identities and actions receive independent budgets.
        rate_limit.check_limit(client, settings, "login", "192.0.2.2", 1)
        rate_limit.check_limit(client, settings, "upload", subject, 1)


@pytest.mark.parametrize("field", ["login_rate_limit_per_minute", "upload_rate_limit_per_minute"])
@pytest.mark.parametrize("value", [0, -1, 10001])
def test_rate_limits_cannot_be_disabled_by_configuration(field, value):
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})
