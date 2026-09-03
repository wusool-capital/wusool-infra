"""The provider-agnostic seam `web_search`'s application service depends on.
Never imports `firecrawl` directly here — swapping providers later means
writing a new implementation of this Protocol, not touching the caller.
"""

from typing import Protocol

from app.modules.matching_engine.domain.web_search import WebSourcedLead


class FirecrawlClient(Protocol):
    async def find_potential_sellers(
        self, *, industry: str, geography: str, limit: int
    ) -> list[WebSourcedLead]: ...
