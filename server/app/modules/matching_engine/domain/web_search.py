"""Web-search domain value objects. No provider/SDK import here."""

from dataclasses import dataclass


@dataclass(frozen=True)
class WebSourcedLead:
    """An unverified seller lead found on Google Maps, outside the CRM."""

    name: str
    source_url: str
    address: str | None = None
    category: str | None = None
