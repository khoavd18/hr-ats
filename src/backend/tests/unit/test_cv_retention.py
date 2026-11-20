from datetime import date

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.workers.tasks import retention_date


@pytest.mark.parametrize(
    ("today", "months", "expected"),
    [
        (date(2026, 11, 8), 24, date(2028, 11, 8)),
        (date(2026, 1, 31), 1, date(2026, 2, 28)),
        (date(2024, 1, 31), 1, date(2024, 2, 29)),
        (date(2024, 2, 29), 12, date(2025, 2, 28)),
        (date(2026, 12, 31), 2, date(2027, 2, 28)),
    ],
)
def test_retention_uses_calendar_months(today, months, expected):
    assert retention_date(today, months) == expected


@pytest.mark.parametrize("months", [0, -1])
def test_retention_configuration_must_be_positive(months):
    with pytest.raises(ValidationError):
        Settings(data_retention_months=months)
