"""Locally-scoped Pydantic models parsing Diffbot's Enhance API response
shape (`GET https://kg.diffbot.com/kg/v3/enhance`) — never exported as this
module's public schema. Only the subset of Diffbot's Organization entity
this module maps to an `EnrichableField` is declared; every field is
optional since Diffbot never guarantees a hit on any of them.

Verified against a live account (`DIFFBOT_API_KEY`, real "Stripe" lookup):
`foundingDate` and `revenue` are nested objects, not bare scalars, and
`location.country` is itself an entity object with its own `name` — none
of that matches Diffbot's own published field reference
(https://docs.diffbot.com/reference/enhance-organization-type), which
this schema was originally written against blind. The same live response
also confirmed `nbLocations`/`logo`/`angellistUri`/`facebookUri`/
`twitterUri` are present and already come back on every Enhance call —
mapped in `client.py` even though the initial field plan missed them.
"""

from pydantic import BaseModel, Field


class DiffbotDate(BaseModel):
    # e.g. "d2010-01-01" — Diffbot prefixes a precision character (day/
    # month/year); `client.py::_parse_founding_date` strips it before
    # parsing.
    text: str | None = Field(default=None, alias="str")


class DiffbotRevenue(BaseModel):
    value: float | None = None
    currency: str | None = None


class DiffbotCountry(BaseModel):
    name: str | None = None


class DiffbotLocation(BaseModel):
    country: DiffbotCountry | None = None


class DiffbotOrganization(BaseModel):
    # camelCase field names are Diffbot's own — kept verbatim to match its
    # response body exactly rather than aliasing.
    name: str | None = None
    description: str | None = None
    foundingDate: DiffbotDate | None = None
    nbEmployeesMin: int | None = None
    nbEmployeesMax: int | None = None
    nbLocations: int | None = None
    revenue: DiffbotRevenue | None = None
    location: DiffbotLocation | None = None
    linkedInUri: str | None = None
    logo: str | None = None
    angellistUri: str | None = None
    facebookUri: str | None = None
    twitterUri: str | None = None
    origin: str | None = None


class DiffbotEnhanceEntity(BaseModel):
    entity: DiffbotOrganization


class DiffbotEnhanceResponse(BaseModel):
    data: list[DiffbotEnhanceEntity] = []
