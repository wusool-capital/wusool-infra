"""Pydantic schemas at the buyer module's external/application boundary.

All nullable DB columns stay `X | None` here — no defaults invented, no
"Unknown" sentinel at this layer (that representation belongs to a future
higher-level application service, not the persistence/schema layer).
"""

from pydantic import BaseModel

from app.shared.types import Money, OrganizationSummary


class BuyerSummary(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    organization: OrganizationSummary
    model: str | None = None
    mandate_status: str | None = None


class BuyerRoleRead(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    org_attio_id: str
    model: str | None = None
    mandate_status: str | None = None
    ebitda_floor: Money | None = None
    check_size_min: Money | None = None
    check_size_max: Money | None = None
    ev_ceiling: Money | None = None
    deal_structure_tolerance: str | None = None
    earnout_tolerance: str | None = None
    profitable_only: bool | None = None
    investment_strategy: str | None = None
    notes: str | None = None
    key_contact_attio_id: str | None = None
    acquisition_enrichment: str | None = None
    deals_introduced: int | None = None
    deals_converted: int | None = None
