"""SQL for a checked `FieldCondition`, shared by every list of buyers or sellers."""

from decimal import Decimal

from sqlalchemy import ColumnElement, Numeric, and_, case, func, or_, true
from sqlalchemy.orm import InstrumentedAttribute

from app.models import BuyerRole, Organization, SellerRole
from app.modules.record_filters.domain.fields import FieldCondition, RecordKind

_NUMERIC_TEXT = r"^\s*-?[0-9]+(\.[0-9]+)?\s*$"
_ROLE_MODELS: dict[RecordKind, type[BuyerRole] | type[SellerRole]] = {
    "buyer": BuyerRole,
    "seller": SellerRole,
}


def joined_text_has(column: InstrumentedAttribute[str | None], value: str) -> ColumnElement[bool]:
    """A multi-select stored as one ", "-joined text (`hq_country`, `region`) holds
    `value` as one of its items, not merely as the whole string."""
    items = func.regexp_split_to_array(column, r"\s*,\s*")
    return func.array_position(items, value).is_not(None)


def money_amount(
    column: InstrumentedAttribute[dict[str, str | float] | None],
) -> ColumnElement[Decimal | None]:
    """The stored USD amount, or NULL when missing or not a number, so one
    malformed row never fails the whole query. A numeric string counts as a number,
    as `get_*` shows it as one."""
    amount = column["amount"]
    return case(
        (func.jsonb_typeof(amount) == "number", amount.astext.cast(Numeric)),
        (
            and_(func.jsonb_typeof(amount) == "string", amount.astext.op("~")(_NUMERIC_TEXT)),
            amount.astext.cast(Numeric),
        ),
        else_=None,
    )


def condition_sql(kind: RecordKind, condition: FieldCondition) -> ColumnElement[bool]:
    """Range and equality tests never match a NULL; use `is_set` to ask about unknowns."""
    model = Organization if condition.target == "org" else _ROLE_MODELS[kind]
    column = getattr(model, condition.column)
    value = condition.value
    op = condition.op
    shape = condition.shape

    if op in ("is_set", "is_not_set"):
        if shape == "array":
            is_set = func.cardinality(column) > 0
        elif shape == "money":
            is_set = money_amount(column).is_not(None)
        elif shape in ("text", "joined_text"):
            is_set = and_(column.is_not(None), column != "")
        else:
            is_set = column.is_not(None)
        return is_set if op == "is_set" else ~is_set
    if op == "in" and isinstance(value, tuple):
        if shape == "array":
            return column.overlap(list(value))
        if shape == "joined_text":
            return or_(*(joined_text_has(column, item) for item in value))
        return column.in_(list(value))
    if op == "contains" and isinstance(value, str):
        return column.icontains(value, autoescape=True)
    if op == "eq" and shape == "array" and isinstance(value, str):
        return column.contains([value])
    if op == "eq" and shape == "joined_text" and isinstance(value, str):
        return joined_text_has(column, value)

    compared = money_amount(column) if shape == "money" else column
    if op == "eq":
        return compared == value
    if op == "gte":
        return compared >= value
    if op == "lte":
        return compared <= value
    return true()  # unreachable: `resolve_filters` only builds valid ops
