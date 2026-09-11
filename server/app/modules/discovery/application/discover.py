"""Search step: find leads outside the CRM for a given industry/geography.
Never persists anything — see the module docstring for why a lead is
ephemeral until an operator turns it into a draft and confirms it.
"""

from app.modules.discovery.application.base import ServiceBase
from app.modules.discovery.domain.leads import DiscoveredLead


class DiscoverMixin(ServiceBase):
    async def find_leads(
        self,
        *,
        industry: str,
        geography: str,
        limit: int,
        exclude_terms: tuple[str, ...] = (),
    ) -> list[DiscoveredLead]:
        if self._lead_search_client is None:
            return []
        return await self._lead_search_client.find_potential_sellers(
            industry=industry, geography=geography, limit=limit, exclude_terms=exclude_terms
        )
