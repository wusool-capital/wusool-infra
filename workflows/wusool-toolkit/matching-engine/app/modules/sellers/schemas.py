"""Pydantic schemas at the seller module's external/application boundary.

All nullable DB columns stay `X | None` here — no defaults invented, no
"Unknown" sentinel at this layer.
"""

import uuid
from datetime import date

from pydantic import BaseModel

from app.shared.types import Money, OrganizationSummary


class SellerSummary(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    organization: OrganizationSummary
    outreach_tier: str | None = None
    relationship_status: str | None = None


class SellerRoleRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    org_attio_id: str
    outreach_tier: str | None = None
    appetite_signal: str | None = None
    relationship_status: str | None = None
    est_revenue: Money | None = None
    est_ebitda: Money | None = None
    owner_salary: Money | None = None
    valuation_low: Money | None = None
    valuation_mid: Money | None = None
    valuation_high: Money | None = None
    sell_timeline: str | None = None
    readiness_score: float | None = None
    readiness_band: str | None = None
    last_attempt_date: date | None = None
    last_attempt_channel: str | None = None
    last_attempt_outcome: str | None = None
    lead_quality_score: float | None = None
    re_engage_date: date | None = None
