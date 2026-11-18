"""Every data column of a buyer or seller role and its company, read from the models,
so a new column is filterable with no code here."""

import uuid
from collections.abc import Sequence
from datetime import date, datetime

from sqlalchemy import ARRAY, TIMESTAMP, Boolean, Date, DateTime, Float, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import class_mapper
from sqlalchemy.types import TypeEngine

from app.models import BuyerRole, Organization, SellerRole
from app.modules.record_filters.domain.fields import (
    FieldCatalog,
    FieldMeta,
    FieldShape,
    FilterableField,
    RecordKind,
)

# Ids, links to other tables, raw payloads, sync bookkeeping and list flags: no advisor
# filters on them.
_INTERNAL = frozenset({"id", "raw_attio", "legacy_entry_id", "removed_at", "is_active"})
# Every Python type the three models store.
ColumnType = TypeEngine[
    str | float | bool | date | datetime | list[str] | dict[str, str | float] | uuid.UUID | None
]
_ROLE_MODELS: dict[RecordKind, type[BuyerRole] | type[SellerRole]] = {
    "buyer": BuyerRole,
    "seller": SellerRole,
}


def build_catalog(kind: RecordKind, meta: Sequence[FieldMeta]) -> FieldCatalog:
    """`meta` are the fields the caller already names (its keys win and they are the
    editable ones). Every other data column follows, keyed by its column name, or
    `role_<name>` / `org_<name>` when that key is taken."""
    columns = {"role": _columns(_ROLE_MODELS[kind]), "org": _columns(Organization)}

    fields: list[FilterableField] = []
    for item in meta:
        column_type = columns[item.target][item.column]
        shape = _shape(column_type)
        if shape == "text" and item.joined_text:
            shape = "joined_text"
        if shape is None:
            raise ValueError(f"{item.target}.{item.column} has a type that cannot be filtered")
        fields.append(
            FilterableField(
                key=item.key,
                target=item.target,
                column=item.column,
                shape=shape,
                label=item.label,
                options=item.options,
                editable=True,
            )
        )

    taken = {f.key for f in fields}
    covered = {(f.target, f.column) for f in fields}
    for target, prefix in (("role", "role_"), ("org", "org_")):
        for column, column_type in columns[target].items():
            shape = _shape(column_type)
            if shape is None or (target, column) in covered or _is_internal(column):
                continue
            key = column if column not in taken else f"{prefix}{column}"
            taken.add(key)
            fields.append(
                FilterableField(
                    key=key,
                    target=target,
                    column=column,
                    shape=shape,
                    label=column.replace("_", " ").capitalize(),
                )
            )
    return FieldCatalog(kind=kind, fields=tuple(fields))


def _columns(
    model: type[BuyerRole] | type[SellerRole] | type[Organization],
) -> dict[str, ColumnType]:
    return {attr.key: attr.columns[0].type for attr in class_mapper(model).column_attrs}


def _is_internal(column: str) -> bool:
    return column in _INTERNAL or column.endswith("attio_id")


def _shape(column_type: ColumnType) -> FieldShape | None:
    if isinstance(column_type, ARRAY):
        return "array"
    if isinstance(column_type, JSONB):
        return "money"  # every JSONB column left after `_INTERNAL` holds {amount, currency}
    if isinstance(column_type, Boolean):
        return "bool"
    if isinstance(column_type, DateTime | TIMESTAMP):
        return "datetime"
    if isinstance(column_type, Date):
        return "date"
    if isinstance(column_type, Integer | Numeric | Float):
        return "number"
    if isinstance(column_type, String):
        return "text"
    return None
