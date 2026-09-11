"""Fakes for discovery's ports — no network, no Slack."""

from app.modules.discovery.application.ports.research import LeadSearchClient
from app.modules.discovery.application.ports.seller_draft import SellerDraftPort
from app.modules.discovery.domain.drafts import SellerDraft
from app.modules.discovery.domain.leads import DiscoveredLead


class FakeLeadSearchClient(LeadSearchClient):
    def __init__(self, leads: list[DiscoveredLead] | None = None) -> None:
        self.leads = leads or []

    async def find_potential_sellers(
        self, *, industry: str, geography: str, limit: int
    ) -> list[DiscoveredLead]:
        return self.leads[:limit]


class FakeSellerDraftPort(SellerDraftPort):
    def __init__(self) -> None:
        self.calls: list[SellerDraft] = []

    async def open_confirm_form(
        self, *, trigger_id: str, draft: SellerDraft, channel_id: str, requested_by: str
    ) -> None:
        self.calls.append(draft)
