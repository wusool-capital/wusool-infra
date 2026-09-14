"""The provider-agnostic seam `DiscoverMixin` depends on. Never imports a
vendor SDK/client directly here — swapping providers (Firecrawl -> Google
Places, see `providers/google_places/`) means writing a new implementation
of this Protocol, not touching the application layer.
"""

from typing import Protocol

from app.modules.discovery.domain.leads import DiscoveredLead


class LeadSearchClient(Protocol):
    async def find_potential_sellers(
        self, *, industry: str, geography: str, limit: int, exclude_terms: tuple[str, ...] = ()
    ) -> list[DiscoveredLead]: ...
