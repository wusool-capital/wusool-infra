"""Pydantic schema for the `organizations` fields `/edit-seller`/
`/edit-buyer`'s field-picker can offer — see `organization_field_spec.py`
for the authoritative eligibility list this must stay in sync with.
"""

from datetime import date

from pydantic import BaseModel, Field


class OrganizationUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=4000)
    hq_country: str | None = Field(default=None, max_length=100)
    sector_focus: list[str] | None = None
    client_type: str | None = Field(default=None, max_length=100)
    relationship_status: str | None = Field(default=None, max_length=100)
    estimated_arr: str | None = Field(default=None, max_length=100)
    funding_raised: float | None = None
    linkedin: str | None = Field(default=None, max_length=500)
    logo_url: str | None = Field(default=None, max_length=500)
    angellist: str | None = Field(default=None, max_length=500)
    facebook: str | None = Field(default=None, max_length=500)
    instagram: str | None = Field(default=None, max_length=500)
    twitter: str | None = Field(default=None, max_length=500)
    twitter_follower_count: int | None = None
    foundation_date: date | None = None
    ticket_size: str | None = Field(default=None, max_length=100)
    lead_source: str | None = Field(default=None, max_length=100)
    employee_range: str | None = Field(default=None, max_length=100)
