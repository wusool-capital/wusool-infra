"""SQL conditions shared by the role repositories' `list_filtered`."""

from sqlalchemy import ColumnElement, func
from sqlalchemy.orm import InstrumentedAttribute


def joined_text_has(column: InstrumentedAttribute[str | None], value: str) -> ColumnElement[bool]:
    """A multi-select stored as one ", "-joined text (`hq_country`, `region`) holds
    `value` as one of its items, not merely as the whole string."""
    items = func.regexp_split_to_array(column, r"\s*,\s*")
    return func.array_position(items, value).is_not(None)
