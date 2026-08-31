"""Pydantic schemas at the buyer module's external/application boundary.

All nullable DB columns stay `X | None` here — no defaults invented, no
"Unknown" sentinel at this layer.
"""

import uuid
from datetime import date

from pydantic import BaseModel, Field

from ddl_commands.shared.types import OrganizationSummary


class BuyerSummary(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    organization: OrganizationSummary
    model: str | None = None
    mandate_status: str | None = None


class BuyerUpdate(BaseModel):
    """Every field `/edit-buyer`'s field-picker can offer — see
    `ddl_commands/modules/buyers/field_spec.py` for the authoritative
    eligibility list this must stay in sync with. Excluded on purpose:
    `mandate_id`-equivalent (buyers have none), `key_contact` (a
    record-reference, deferred), `key_personnel` (intentionally not
    exposed), `raw_attio`/timestamps (system-managed),
    `acquisition_enrichment`/`deals_introduced`/`deals_converted`
    (ownership: both manual and pipeline-written — see plan.md Part C).

    Select-kind fields are typed as plain `str` — the Slack UI itself only
    ever submits one of `field_spec.py`'s fixed option titles. Money fields
    are a bare `float` amount — currency is fixed per field now, never user
    input (see `ddl_commands/shared/attio/money.py`). `earnout_tolerance` is
    a real `bool` column since #53 (`database/sync-postgres.ps1` parses it
    with the same `boolean()` function as `profitable_only`).
    """

    model: str | None = Field(default=None, max_length=100)
    mandate_status: str | None = Field(default=None, max_length=100)
    deal_structure_tolerance: str | None = Field(default=None, max_length=200)
    earnout_tolerance: bool | None = None
    profitable_only: bool | None = None
    investment_strategy: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=4000)
    ebitda_floor: float | None = None
    check_size_min: float | None = None
    check_size_max: float | None = None
    ev_ceiling: float | None = None
    ebitda_ceiling: float | None = None
    estimated_aum: float | None = None
    notable_investments: str | None = Field(default=None, max_length=2000)
    relationship_warmth: str | None = Field(default=None, max_length=100)
    target_geography: list[str] | None = None
    last_mandate_briefing_date: date | None = None
    prior_gcc_acquisition: str | None = Field(default=None, max_length=100)
