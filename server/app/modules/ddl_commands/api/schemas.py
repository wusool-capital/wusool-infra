"""Shared DTOs/field-spec types used across more than one concept's own
`api/<concept>.py`.
"""

from dataclasses import dataclass
from datetime import date
from typing import Literal

from pydantic import BaseModel

from app.modules.utilities.domain.json_types import JsonObject

# A "bool_as_text" kind used to live here for `buyer_roles.earnout_tolerance`
# alone — boolean in Attio, `text` in Postgres. #53 made the column a real
# boolean, so the workaround and its stringify/parse round trip are gone.
#
# "number" vs "percent": both render a Slack `number_input` and pass through
# bare to Attio, but "number" maps to an `Integer` column and hard-casts to
# `int` (built for `twitter_follower_count`), while "percent" maps to
# `Numeric` and keeps decimal precision (e.g. `12.5`) for percentage-shaped
# columns like `seller_roles.gross_margin_pct`.
# "multi_select_text" vs "multi_select_as_text": both render Slack's
# multi-select over `options`, but the first is a real Attio multi-select
# (option IDs out, `text[]` column) while the second is a plain Attio `text`
# attribute the operators pick into — titles joined with ", " on the way out,
# split back on the way in. `organizations.client_type` is the latter: text in
# Attio, so a bare string, but a fixed vocabulary operators shouldn't retype.
FieldKind = Literal[
    "text",
    "multiline",
    "select",
    "multi_select_text",
    "multi_select_as_text",
    "currency",
    "date",
    "bool",
    "number",
    "percent",
]


@dataclass(frozen=True)
class FieldSpec:
    name: str
    label: str
    kind: FieldKind
    options: tuple[str, ...] = ()


# Every shape a field's value can take across `FieldKind`, at either its
# already-stored ORM-column shape or a prefill source's raw shape (a bare
# currency amount before `wrap_prefill_value` wraps it into the
# `{"amount": ...}` shape a stored role/org row already carries). Mirrors
# `enrichment.domain.proposals.FieldValue` — same underlying concept
# (whatever a dynamically-typed field's value looks like), kept as this
# module's own type rather than a cross-module import since `FieldKind`
# here is `ddl_commands`' own vocabulary, not enrichment's.
PrefillValue = str | float | bool | int | date | list[str] | JsonObject


class OrganizationSummary(BaseModel):
    """Slim organization view embedded in both buyer and seller schemas.
    Deliberately duplicated in `matching_engine/api/schemas.py`, not shared —
    a plain presentation DTO, not cross-cutting logic.
    """

    model_config = {"from_attributes": True}

    attio_id: str
    name: str
    hq_country: str | None = None
    geographic_focus: list[str] = []
    sector_focus: list[str] = []
    relationship_status: str | None = None
