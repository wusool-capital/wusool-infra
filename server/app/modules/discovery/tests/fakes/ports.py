"""Fakes for discovery's ports — no network, no Slack."""

import asyncio
from uuid import uuid4

from app.modules.discovery.application.ports.research import LeadSearchClient
from app.modules.discovery.application.ports.seller_draft import SellerDraftPort
from app.modules.discovery.application.ports.seller_writer import SellerWriterPort
from app.modules.discovery.domain.crm import CrmMatch, CrmMatchKind
from app.modules.discovery.domain.drafts import SellerDraft
from app.modules.discovery.domain.leads import DiscoveredLead
from app.modules.discovery.domain.outcome import CreatedSeller, SellerWriteError


class FakeLeadSearchClient(LeadSearchClient):
    def __init__(self, leads: list[DiscoveredLead] | None = None) -> None:
        self.leads = leads or []
        self.calls: list[tuple[str, str, tuple[str, ...]]] = []

    async def find_potential_sellers(
        self, *, industry: str, geography: str, limit: int, exclude_terms: tuple[str, ...] = ()
    ) -> list[DiscoveredLead]:
        self.calls.append((industry, geography, exclude_terms))
        return self.leads[:limit]


class FakeSellerDraftPort(SellerDraftPort):
    def __init__(self) -> None:
        self.calls: list[SellerDraft] = []

    async def open_confirm_form(
        self, *, trigger_id: str, draft: SellerDraft, channel_id: str, requested_by: str
    ) -> None:
        self.calls.append(draft)


class FakeSellerWriterPort(SellerWriterPort):
    """`matches` maps a lead name to its CRM match (default: no match);
    `fail_names` raise `SellerWriteError` on create."""

    def __init__(
        self,
        matches: dict[str, CrmMatch] | None = None,
        fail_names: frozenset[str] = frozenset(),
        create_delay_s: float = 0.0,
    ) -> None:
        self.matches = matches or {}
        self.fail_names = fail_names
        self.create_delay_s = create_delay_s
        self.created: list[SellerDraft] = []
        self.timeouts: list[float] = []
        self.in_flight = 0
        self.max_in_flight = 0

    async def find_existing(self, lead: DiscoveredLead) -> CrmMatch:
        return self.matches.get(lead.name, CrmMatch(kind=CrmMatchKind.NONE))

    async def enrich_and_create(
        self, draft: SellerDraft, *, enrichment_timeout_s: float
    ) -> CreatedSeller:
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(self.create_delay_s)
            if draft.org_name in self.fail_names:
                raise SellerWriteError("attio down", landed=("organization created in Attio",))
            self.created.append(draft)
            self.timeouts.append(enrichment_timeout_s)
            return CreatedSeller(
                seller_role_id=uuid4(),
                org_attio_id=f"attio-{draft.org_name}",
                org_name=draft.org_name,
                source_url=draft.source_urls[0] if draft.source_urls else "",
                place_id=draft.source_place_id,
            )
        finally:
            self.in_flight -= 1
