"""Pydantic schemas at the buyer module's external/application boundary.

All nullable DB columns stay `X | None` here — no defaults invented, no
"Unknown" sentinel at this layer.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.shared.types import OrganizationSummary


class BuyerSummary(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    organization: OrganizationSummary
    model: str | None = None
    mandate_status: str | None = None
    archived_at: datetime | None = None


class MoneyInput(BaseModel):
    amount: float | None = None
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")


class BuyerUpdate(BaseModel):
    """Every user-editable `buyer_roles` field. Excluded on purpose:
    `mandate_id`-equivalent (buyers have none), `key_contact_attio_id` (needs
    a Person's Attio ID, not a natural Slack input), `raw_attio`/timestamps/
    `archived_at`/`bot_managed_at`/`bot_managed_by` (system-managed — the use
    case sets these, never the form).

    `max_length` caps are conservative UX guesses, not sourced from any
    documented product limit — adjust later only if a real user hits one.
    """

    model: str | None = Field(default=None, max_length=100)
    mandate_status: str | None = Field(default=None, max_length=100)
    ebitda_floor: MoneyInput | None = None
    check_size_min: MoneyInput | None = None
    check_size_max: MoneyInput | None = None
    ev_ceiling: MoneyInput | None = None
    deal_structure_tolerance: str | None = Field(default=None, max_length=200)
    earnout_tolerance: str | None = Field(default=None, max_length=200)
    profitable_only: bool | None = None
    investment_strategy: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=4000)
    acquisition_enrichment: str | None = Field(default=None, max_length=2000)
    deals_introduced: int | None = Field(default=None, ge=0)
    deals_converted: int | None = Field(default=None, ge=0)
