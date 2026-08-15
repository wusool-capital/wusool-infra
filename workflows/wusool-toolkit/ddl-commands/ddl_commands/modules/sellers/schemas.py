"""Pydantic schemas at the seller module's external/application boundary.

All nullable DB columns stay `X | None` here — no defaults invented, no
"Unknown" sentinel at this layer.
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from ddl_commands.shared.types import OrganizationSummary


class SellerSummary(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    organization: OrganizationSummary
    outreach_tier: str | None = None
    relationship_status: str | None = None
    removed_at: datetime | None = None


class MoneyInput(BaseModel):
    amount: float | None = None
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")


class SellerUpdate(BaseModel):
    """Every user-editable `seller_roles` field. Excluded on purpose:
    `mandate_id` (needs a mandate UUID, not a natural Slack input),
    `raw_attio`/timestamps/`removed_at`/`bot_managed_at`/`bot_managed_by`
    (system-managed — the use case sets these, never the form).

    `max_length` caps and the 0-100 range on the two score fields are
    explicit, documented product decisions (not guesses left open) — see
    plan.md's Context section for the reasoning.
    """

    outreach_tier: str | None = Field(default=None, max_length=100)
    appetite_signal: str | None = Field(default=None, max_length=100)
    relationship_status: str | None = Field(default=None, max_length=100)
    est_revenue: MoneyInput | None = None
    est_ebitda: MoneyInput | None = None
    owner_salary: MoneyInput | None = None
    valuation_low: MoneyInput | None = None
    valuation_mid: MoneyInput | None = None
    valuation_high: MoneyInput | None = None
    sell_timeline: str | None = Field(default=None, max_length=100)
    readiness_score: float | None = Field(default=None, ge=0, le=100)
    readiness_band: str | None = Field(default=None, max_length=100)
    intake_source: str | None = Field(default=None, max_length=100)
    last_attempt_date: date | None = None
    last_attempt_channel: str | None = Field(default=None, max_length=100)
    last_attempt_outcome: str | None = Field(default=None, max_length=500)
    lead_quality_score: float | None = Field(default=None, ge=0, le=100)
    re_engage_date: date | None = None
