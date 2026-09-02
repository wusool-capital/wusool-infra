"""The provider-agnostic seam `web_search`'s application service depends on.
Never imports `firecrawl` directly here — swapping providers later means
writing a new implementation of this Protocol, not touching the caller.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class WebSourcedLead:
    """An unverified seller lead found on Google Maps, outside the CRM."""

    name: str
    source_url: str
    address: str | None = None
    category: str | None = None


class FirecrawlClient(Protocol):
    async def find_potential_sellers(
        self, *, industry: str, geography: str, limit: int
    ) -> list[WebSourcedLead]: ...
