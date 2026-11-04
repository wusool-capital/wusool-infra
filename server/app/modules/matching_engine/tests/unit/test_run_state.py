from datetime import UTC, datetime, timedelta

import pytest

from app.modules.matching_engine.domain.matching.run_state import run_state

_NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
_STALE_AFTER = timedelta(minutes=15)


@pytest.mark.parametrize(
    ("status", "age", "completed", "expected"),
    [
        ("GENERATED", timedelta(minutes=1), False, "running"),
        ("GENERATED", timedelta(minutes=16), False, "stale"),
        ("GENERATED", timedelta(minutes=1), True, "completed"),
        ("FAILED", timedelta(minutes=1), True, "failed"),
        ("FAILED", timedelta(hours=2), True, "failed"),
    ],
)
def test_run_state(status: str, age: timedelta, completed: bool, expected: str) -> None:
    started_at = _NOW - age
    state = run_state(
        status=status,
        started_at=started_at,
        completed_at=_NOW if completed else None,
        now=_NOW,
        stale_after=_STALE_AFTER,
    )
    assert state == expected
