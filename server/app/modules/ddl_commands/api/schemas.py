"""Shared DTOs/field-spec types used across more than one concept's own
`api/<concept>.py`.
"""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

# A "bool_as_text" kind used to live here for `buyer_roles.earnout_tolerance`
# alone — boolean in Attio, `text` in Postgres. #53 made the column a real
# boolean, so the workaround and its stringify/parse round trip are gone.
#
# "number" vs "percent": both render a Slack `number_input` and pass through
# bare to Attio, but "number" maps to an `Integer` column and hard-casts to
# `int` (built for `twitter_follower_count`), while "percent" maps to
# `Numeric` and keeps decimal precision (e.g. `12.5`) for percentage-shaped
# columns like `seller_roles.gross_margin_pct`.
FieldKind = Literal[
    "text",
    "multiline",
    "select",
    "multi_select_text",
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
