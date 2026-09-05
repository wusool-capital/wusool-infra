"""Locally-scoped Pydantic models parsing Firecrawl's Google Maps scrape
response shape — never exported as this module's public schema."""

from pydantic import BaseModel


class _Business(BaseModel):
    name: str
    address: str | None = None
    category: str | None = None


class MapsExtraction(BaseModel):
    businesses: list[_Business]
