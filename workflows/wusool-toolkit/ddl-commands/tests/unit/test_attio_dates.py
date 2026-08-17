from datetime import UTC, date, datetime

import pytest

from ddl_commands.shared.attio.dates import UnknownDateFieldError, serialize_date


def test_plain_date_field_serializes_without_time() -> None:
    assert serialize_date("last_attempt_date", date(2026, 3, 5)) == "2026-03-05"
    assert serialize_date("re_engage_date", date(2026, 12, 25)) == "2026-12-25"


def test_timestamp_field_serializes_full_iso() -> None:
    value = datetime(2026, 3, 5, 14, 30, tzinfo=UTC)
    result = serialize_date("last_interaction_at", value)
    assert result == value.isoformat()
    assert "T" in result


def test_timestamp_field_rejects_plain_date() -> None:
    with pytest.raises(UnknownDateFieldError):
        serialize_date("last_interaction_at", date(2026, 3, 5))


def test_unknown_field_raises() -> None:
    with pytest.raises(UnknownDateFieldError):
        serialize_date("not_a_real_field", date(2026, 1, 1))
