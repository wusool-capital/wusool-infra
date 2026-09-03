"""Pydantic schemas at the seller concept's external/application boundary.

All nullable DB columns stay `X | None` here — no defaults invented, no
"Unknown" sentinel at this layer.

Note: neither schema below has a consumer within `matching_engine` today
(carried over as-is from the pre-restructure file, not deleted — see
CLAUDE.md's "don't remove pre-existing dead code unless asked").
"""

import uuid
from datetime import date

from pydantic import BaseModel

from app.modules.matching_engine.api.schemas import OrganizationSummary
from app.modules.utilities import Money


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
