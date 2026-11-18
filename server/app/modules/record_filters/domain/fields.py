"""The columns of a buyer or seller (with its company) that can be filtered, and the
checked conditions on them. Framework-free: the SQL lives in `persistence/`."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

RecordKind = Literal["buyer", "seller"]
# How a column is stored, not how its form field looks: a ", "-joined text and a text
# array are both multi-selects but need different SQL.
FieldShape = Literal["text", "array", "joined_text", "money", "number", "date", "datetime", "bool"]
FilterOp = Literal["eq", "in", "contains", "gte", "lte", "is_set", "is_not_set"]
ConditionValue = str | float | bool | date | datetime | tuple[str, ...] | None

_SET_OPS: tuple[FilterOp, ...] = ("is_set", "is_not_set")
ALLOWED_OPS: dict[FieldShape, tuple[FilterOp, ...]] = {
    "text": ("eq", "in", "contains", *_SET_OPS),
    "array": ("in", "eq", *_SET_OPS),
    "joined_text": ("in", "eq", *_SET_OPS),
    "money": ("gte", "lte", "eq", *_SET_OPS),
    "number": ("gte", "lte", "eq", *_SET_OPS),
    "date": ("gte", "lte", "eq", *_SET_OPS),
    "datetime": ("gte", "lte", *_SET_OPS),
    "bool": ("eq", *_SET_OPS),
}


@dataclass(frozen=True)
class FieldMeta:
    """What the caller knows about a column that the model cannot say: the key the
    caller already uses for it, its label, and its select options."""

    key: str
    target: Literal["role", "org"]  # the buyer/seller role, or its company
    column: str
    label: str
    options: tuple[str, ...] = ()
    joined_text: bool = False


@dataclass(frozen=True)
class FilterableField:
    key: str
    target: Literal["role", "org"]
    column: str
    shape: FieldShape
    label: str
    options: tuple[str, ...] = ()
    editable: bool = False  # false for computed or synced columns

    @property
    def ops(self) -> tuple[FilterOp, ...]:
        return ALLOWED_OPS[self.shape]


@dataclass(frozen=True)
class FieldCatalog:
    kind: RecordKind
    fields: tuple[FilterableField, ...]

    def get(self, key: str) -> FilterableField | None:
        return next((f for f in self.fields if f.key == key), None)


@dataclass(frozen=True)
class FieldCondition:
    """One checked filter. `column` comes from a catalog field, never from a caller."""

    target: Literal["role", "org"]
    column: str
    shape: FieldShape
    op: FilterOp
    value: ConditionValue = None


@dataclass(frozen=True)
class FilterProblem:
    """`message` is complete on its own, for the agent that sent the filter."""

    position: int  # 1-based position in the filter list
    field: str
    kind: Literal["unknown_field", "not_allowed", "invalid"]
    message: str
