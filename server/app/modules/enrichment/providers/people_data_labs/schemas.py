"""Locally-scoped Pydantic model parsing People Data Labs' Company
Enrichment API response shape (`GET /v5/company/enrich`) — never exported
as this module's public schema. Only the subset this module maps to an
`EnrichableField` is declared.

Schema written against PDL's own published response reference
(https://docs.peopledatalabs.com/docs/company-enrichment-api), not verified
against a live account — this repo has no PDL API key to test against.
Confirm response shape (in particular whether `estimated_num_employees`
and `location.country` are populated on the free tier for a given company)
before relying on this in production.
"""

from pydantic import BaseModel


class PdlLocation(BaseModel):
    country: str | None = None


class PdlCompanyResponse(BaseModel):
    status: int | None = None
    name: str | None = None
    summary: str | None = None
    founded: int | None = None
    estimated_num_employees: int | None = None
    linkedin_url: str | None = None
    location: PdlLocation | None = None
    website: str | None = None
