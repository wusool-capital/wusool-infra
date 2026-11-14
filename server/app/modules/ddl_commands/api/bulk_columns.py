"""Human-readable columns for a bulk upload file, and the conversion of one cell
to the value the Slack add forms produce for the same field.

The columns are built from the `FieldSpec`s, so a template can't drift from the
fields the add forms accept.
"""

import csv
import io
import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from app.modules.ddl_commands.api.bulk_store import UploadKind
from app.modules.ddl_commands.api.buyers import BUYER_ROLE_FIELDS
from app.modules.ddl_commands.api.organizations import ORGANIZATION_FIELDS
from app.modules.ddl_commands.api.schemas import FieldSpec, PrefillValue
from app.modules.ddl_commands.api.sellers import SELLER_ROLE_FIELDS

ORG_NAME_LABEL = "Organization name"
DOMAIN_LABEL = "Domain"

# Cells arrive as text from a CSV and already typed from an Excel sheet.
CellValue = str | float | int | bool | date | None

_LIST_SEPARATOR = ";"
_TRUE = frozenset({"yes", "y", "true", "1"})
_FALSE = frozenset({"no", "n", "false", "0"})
_MAX_SHOWN_OPTIONS = 8
# The seller role and the organization both have "Relationship status".
_LABEL_OVERRIDES: dict[tuple[UploadKind, str], str] = {
    ("seller", "relationship_status"): "Seller relationship status",
}


class CellError(Exception):
    """One cell can't become its field's value. The message is safe to show."""


@dataclass(frozen=True)
class Column:
    label: str
    field: str  # key in an upload row
    spec: FieldSpec | None  # None for the organization name and the domain
    required: bool


@dataclass(frozen=True)
class FieldRoute:
    """Where a row key goes: to the organization or to the role, under `name`."""

    key: str
    target: Literal["org", "role"]
    name: str
    spec: FieldSpec


def normalize_label(label: str) -> str:
    return " ".join(label.lower().split())


def routes_for(kind: UploadKind) -> dict[str, FieldRoute]:
    """Row key -> route. A name both the role and the organization have (a seller's
    `relationship_status`) keeps its plain key for the role, and the organization's
    becomes `org_<name>`, so one cell can't be written to both.
    """
    role_fields = BUYER_ROLE_FIELDS if kind == "buyer" else SELLER_ROLE_FIELDS
    role_names = {f.name for f in role_fields}
    routes = {f.name: FieldRoute(f.name, "role", f.name, f) for f in role_fields}
    for f in ORGANIZATION_FIELDS:
        if f.name == "domains":  # filled from the single Domain column
            continue
        key = f"org_{f.name}" if f.name in role_names else f.name
        routes[key] = FieldRoute(key, "org", f.name, f)
    return routes


def columns_for(kind: UploadKind) -> tuple[Column, ...]:
    """Required columns first, then the role's fields, then the organization's."""
    routes = routes_for(kind)
    columns = [
        Column(ORG_NAME_LABEL, "org_name", None, required=True),
        Column(DOMAIN_LABEL, "domain", None, required=True),
    ]
    if kind == "buyer":
        vertical = routes["target_vertical"]
        columns.append(Column(vertical.spec.label, vertical.key, vertical.spec, required=True))
    columns += [
        Column(_LABEL_OVERRIDES.get((kind, r.key), r.spec.label), r.key, r.spec, required=False)
        for r in routes.values()
        if r.key != "target_vertical"
    ]
    return tuple(columns)


def template_csv(kind: UploadKind) -> bytes:
    """The header row only. `utf-8-sig` so Excel reads Arabic text correctly."""
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\r\n").writerow([c.label for c in columns_for(kind)])
    return buffer.getvalue().encode("utf-8-sig")


def coerce_cell(spec: FieldSpec, raw: CellValue) -> PrefillValue | None:
    """An empty cell is unset (`None`). Anything else becomes the value the Slack
    form would have produced, or raises `CellError`."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    match spec.kind:
        case "text" | "multiline":
            return _text(raw)
        case "select":
            return _option(spec, _text(raw))
        case "multi_select_text":
            return _options(spec, _items(raw))
        case "multi_select_as_text":
            return ", ".join(_items(raw))
        case "currency":
            return _number(raw, "an amount")
        case "percent":
            return _number(raw, "a number")
        case "number":
            value = _number(raw, "a whole number")
            if not value.is_integer():
                raise CellError("must be a whole number")
            return int(value)
        case "date":
            return _date(raw)
        case "bool":
            return _bool(raw)
        case _:
            raise CellError("this column is not supported")


def _text(raw: CellValue) -> str:
    if isinstance(raw, float) and raw.is_integer():
        return str(int(raw))
    return str(raw).strip()


def _items(raw: CellValue) -> list[str]:
    items = [part.strip() for part in _text(raw).split(_LIST_SEPARATOR)]
    return [item for item in items if item]


def _shown_options(spec: FieldSpec) -> str:
    shown = ", ".join(spec.options[:_MAX_SHOWN_OPTIONS])
    return f"{shown}, ..." if len(spec.options) > _MAX_SHOWN_OPTIONS else shown


def _option(spec: FieldSpec, text: str) -> str:
    by_lower = {option.lower(): option for option in spec.options}
    if text.lower() in by_lower:
        return by_lower[text.lower()]
    raise CellError(f"not an allowed value. Allowed: {_shown_options(spec)}")


def _options(spec: FieldSpec, items: list[str]) -> list[str]:
    by_lower = {option.lower(): option for option in spec.options}
    unknown = [item for item in items if item.lower() not in by_lower]
    if unknown:
        raise CellError(
            f"not an allowed value: {'; '.join(unknown)}. Allowed: {_shown_options(spec)}"
        )
    return [by_lower[item.lower()] for item in items]


def _number(raw: CellValue, noun: str) -> float:
    if isinstance(raw, str):
        text = raw.strip().replace(",", "").replace("$", "").replace("%", "").replace(" ", "")
        try:
            value = float(text)
        except ValueError:
            raise CellError(f"must be {noun}") from None
    elif isinstance(raw, int | float) and not isinstance(raw, bool):
        value = float(raw)
    else:
        raise CellError(f"must be {noun}")
    if not math.isfinite(value):
        raise CellError(f"must be {noun}")
    return value


def _date(raw: CellValue) -> date:
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw).strip())
    except ValueError:
        raise CellError("use the date format YYYY-MM-DD") from None


def _bool(raw: CellValue) -> bool:
    if isinstance(raw, bool):
        return raw
    text = str(raw).strip().lower()
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    raise CellError("use Yes or No")
