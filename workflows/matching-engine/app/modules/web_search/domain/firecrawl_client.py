"""The provider-agnostic seam `web_search`'s application service depends on.
Never imports `firecrawl` directly here — swapping providers later means
writing a new implementation of this Protocol, not touching the caller.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class WebSourcedLead:
    """An unverified seller lead found outside the CRM. `address`/`category`
    populate from a Maps-scrape result; `snippet` populates from the
    plain-search fallback — never fabricate a field the source can't back.
    """

    name: str
    source_url: str
    address: str | None = None
    category: str | None = None
    snippet: str | None = None


class FirecrawlClient(Protocol):
    async def find_potential_sellers(
        self, *, industry: str, geography: str, limit: int
    ) -> list[WebSourcedLead]: ...
