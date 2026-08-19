"""Pydantic schemas at the seller module's external/application boundary.

All nullable DB columns stay `X | None` here — no defaults invented, no
"Unknown" sentinel at this layer.
"""

import uuid
from datetime import date

from pydantic import BaseModel, Field

from ddl_commands.shared.types import OrganizationSummary


class SellerSummary(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    organization: OrganizationSummary
    outreach_tier: str | None = None
    relationship_status: str | None = None


class SellerUpdate(BaseModel):
    """Every field `/edit-seller`'s field-picker can offer — see
    `ddl_commands/modules/sellers/field_spec.py` for the authoritative
    eligibility list this must stay in sync with. Excluded on purpose:
    `mandate_id` (needs a mandate UUID, not a natural Slack input),
    `raw_attio`/timestamps (system-managed), `readiness_score`/
    `readiness_band`/`lead_quality_score` (ownership: both manual and
    pipeline-written, or zero Attio options defined — see plan.md Part C).

    Select-kind fields (`outreach_tier`, `appetite_signal`, etc.) are typed
    as plain `str` — the Slack UI itself only ever submits one of
    `field_spec.py`'s fixed option titles (`select_block`'s `static_select`
    has no free-text path), so a stricter enum-style check here would be
    redundant, not safer. Money fields are a bare `float` amount, not
    `{"amount", "currency"}` — currency is fixed per field now (see
    `ddl_commands/shared/attio/money.py`), never user input.
    """

    outreach_tier: str | None = Field(default=None, max_length=100)
    appetite_signal: str | None = Field(default=None, max_length=100)
    relationship_status: str | None = Field(default=None, max_length=100)
    sell_timeline: str | None = Field(default=None, max_length=100)
    last_attempt_date: date | None = None
    last_attempt_channel: str | None = Field(default=None, max_length=100)
    last_attempt_outcome: str | None = Field(default=None, max_length=500)
    re_engage_date: date | None = None
    est_revenue: float | None = None
    est_ebitda: float | None = None
    owner_salary: float | None = None
    valuation_low: float | None = None
    valuation_mid: float | None = None
    valuation_high: float | None = None
