from datetime import UTC, datetime

import pytest

from app.modules.interactions.domain.windows import months_before


@pytest.mark.parametrize(
    ("moment", "months", "expected"),
    [
        (datetime(2026, 11, 5, 12, 30, tzinfo=UTC), 12, datetime(2025, 11, 5, 12, 30, tzinfo=UTC)),
        (datetime(2026, 11, 5, tzinfo=UTC), 1, datetime(2026, 10, 5, tzinfo=UTC)),
        (datetime(2026, 1, 15, tzinfo=UTC), 2, datetime(2025, 11, 15, tzinfo=UTC)),
        (datetime(2026, 3, 31, tzinfo=UTC), 1, datetime(2026, 2, 28, tzinfo=UTC)),
        (datetime(2024, 3, 31, tzinfo=UTC), 1, datetime(2024, 2, 29, tzinfo=UTC)),
        (datetime(2026, 5, 31, tzinfo=UTC), 12, datetime(2025, 5, 31, tzinfo=UTC)),
        (datetime(2026, 11, 5, tzinfo=UTC), 0, datetime(2026, 11, 5, tzinfo=UTC)),
    ],
)
def test_months_before_keeps_the_time_and_clamps_short_months(
    moment: datetime, months: int, expected: datetime
) -> None:
    assert months_before(moment, months) == expected
