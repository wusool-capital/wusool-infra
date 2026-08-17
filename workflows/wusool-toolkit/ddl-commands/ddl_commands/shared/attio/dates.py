"""Attio has two distinct date-like attribute types, confirmed live —
writing the wrong shape to the wrong one is a real failure mode, not a
formatting nicety:

- `date`: plain calendar date, no time component (`last_attempt_date`,
  `re_engage_date`).
- `timestamp`: full ISO-8601 with timezone (`last_interaction_at`).
"""

from datetime import date, datetime

_PLAIN_DATE_FIELDS = {"last_attempt_date", "re_engage_date"}
_TIMESTAMP_FIELDS = {"last_interaction_at"}


class UnknownDateFieldError(Exception):
    pass


def serialize_date(field: str, value: date | datetime) -> str:
    if field in _PLAIN_DATE_FIELDS:
        return value.strftime("%Y-%m-%d")
    if field in _TIMESTAMP_FIELDS:
        if not isinstance(value, datetime):
            raise UnknownDateFieldError(f"{field} is a timestamp field but got a plain date")
        return value.isoformat()
    raise UnknownDateFieldError(f"No configured date type for field {field!r}")
