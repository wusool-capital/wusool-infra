"""Filters on any buyer or seller field, in the shape an agent or a web client sends,
and their check against the field's type before any query runs."""

from collections.abc import Sequence
from datetime import UTC, date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.record_filters.domain.fields import (
    ConditionValue,
    FieldCatalog,
    FieldCondition,
    FilterableField,
    FilterProblem,
)

MAX_FILTERS = 10
MAX_VALUES = 20


class _Filter(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    field: str = Field(description="A field key from list_field_options, e.g. ebitda_ceiling")


class InFilter(_Filter):
    op: Literal["in"]
    value: list[str] = Field(
        min_length=1, max_length=MAX_VALUES, description="Matches when any of these match"
    )


class EqFilter(_Filter):
    op: Literal["eq"]
    value: str | float | bool


class ContainsFilter(_Filter):
    op: Literal["contains"]
    value: str = Field(min_length=1, max_length=100, description="Text anywhere in the value")


class GteFilter(_Filter):
    op: Literal["gte"]
    value: float | str = Field(description="A number, or a YYYY-MM-DD date")


class LteFilter(_Filter):
    op: Literal["lte"]
    value: float | str = Field(description="A number, or a YYYY-MM-DD date")


class IsSetFilter(_Filter):
    op: Literal["is_set"]


class IsNotSetFilter(_Filter):
    op: Literal["is_not_set"]


FieldFilter = Annotated[
    InFilter | EqFilter | ContainsFilter | GteFilter | LteFilter | IsSetFilter | IsNotSetFilter,
    Field(discriminator="op"),
]


class _BadValueError(Exception):
    """The message is safe to show and names the field."""


def resolve_filters(
    catalog: FieldCatalog, filters: Sequence[FieldFilter]
) -> tuple[tuple[FieldCondition, ...], list[FilterProblem]]:
    """Every problem is collected, so the caller fixes them all in one go."""
    conditions: list[FieldCondition] = []
    problems: list[FilterProblem] = []
    for position, item in enumerate(filters, start=1):
        field = catalog.get(item.field)
        if field is None:
            message = f"'{item.field}' is not a field of a {catalog.kind}. Call list_field_options"
            problems.append(FilterProblem(position, item.field, "unknown_field", message))
            continue
        if item.op not in field.ops:
            allowed = ", ".join(field.ops)
            message = f"'{item.op}' does not apply to {item.field} ({field.shape}). Use: {allowed}"
            problems.append(FilterProblem(position, item.field, "not_allowed", message))
            continue
        try:
            value = _value(field, item)
        except _BadValueError as error:
            problems.append(FilterProblem(position, item.field, "invalid", str(error)))
            continue
        conditions.append(FieldCondition(field.target, field.column, field.shape, item.op, value))
    return tuple(conditions), problems


def _value(field: FilterableField, item: FieldFilter) -> ConditionValue:
    key = item.field
    if isinstance(item, IsSetFilter | IsNotSetFilter):
        return None
    if isinstance(item, InFilter):
        return tuple(_spelled(field, text) for text in item.value)
    if isinstance(item, ContainsFilter):
        return item.value
    if field.shape in ("text", "array", "joined_text"):
        if not isinstance(item.value, str):
            raise _BadValueError(f"{key} takes text")
        return _spelled(field, item.value)
    if field.shape == "bool":
        if not isinstance(item.value, bool):
            raise _BadValueError(f"{key} takes true or false")
        return item.value
    if field.shape == "date":
        day = _day(item.value)
        if day is None:
            raise _BadValueError(f"{key} takes a YYYY-MM-DD date")
        return day
    if field.shape == "datetime":
        moment = _moment(item.value)
        if moment is None:
            raise _BadValueError(f"{key} takes a YYYY-MM-DD date or an ISO date and time")
        return moment
    number = _number(item.value)
    if number is None:
        raise _BadValueError(f"{key} takes a number, in the units get_* shows")
    return number


def _spelled(field: FilterableField, text: str) -> str:
    """The field's own spelling of `text`; any text when the field has no options."""
    if not field.options:
        return text
    lowered = text.strip().lower()
    matched = next((option for option in field.options if option.lower() == lowered), None)
    if matched is None:
        raise _BadValueError(
            f"'{text}' is not allowed for {field.key}. Call list_field_options for its exact values"
        )
    return matched


def _number(value: str | float | bool) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return float(value)


def _day(value: str | float | bool) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _moment(value: str | float | bool) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)
