"""Slim organization view embedded in both buyer and seller Pydantic schemas."""

from pydantic import BaseModel


class OrganizationSummary(BaseModel):
    model_config = {"from_attributes": True}

    attio_id: str
    name: str
    hq_country: str | None = None
    geographic_focus: list[str] = []
    sector_focus: list[str] = []
    relationship_status: str | None = None
