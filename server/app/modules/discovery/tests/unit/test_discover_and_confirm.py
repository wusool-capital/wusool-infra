import pytest

from app.modules.discovery.application.base import CreationPolicy
from app.modules.discovery.application.service import DiscoveryService
from app.modules.discovery.domain.drafts import SellerDraft
from app.modules.discovery.domain.leads import DiscoveredLead
from app.modules.discovery.tests.fakes.ports import (
    FakeLeadSearchClient,
    FakeReviewStore,
    FakeSellerDraftPort,
    FakeSellerWriterPort,
)
from app.modules.utilities import FixedWindowRateLimiter, NotFoundError


def _service(
    *, lead_search_client=None, store: FakeReviewStore | None = None
) -> tuple[DiscoveryService, FakeSellerDraftPort]:
    draft_port = FakeSellerDraftPort()
    service = DiscoveryService(
        lead_search_client=lead_search_client,
        seller_draft_port=draft_port,
        seller_writer_port=FakeSellerWriterPort(),
        review_store=store or FakeReviewStore(),
        search_limiter=FixedWindowRateLimiter(limit=10),
        policy=CreationPolicy(lead_limit=5, enrichment_concurrency=2, enrichment_budget_s=30.0),
    )
    return service, draft_port


async def test_find_leads_returns_empty_when_no_search_client_configured() -> None:
    service, _ = _service(lead_search_client=None)

    leads = await service.find_leads(industry="Retail", geography="UAE", limit=3)

    assert leads == []


async def test_find_leads_delegates_to_the_search_client_with_the_given_limit() -> None:
    leads = [DiscoveredLead(name=f"Lead {i}", source_url="https://example.com") for i in range(5)]
    service, _ = _service(lead_search_client=FakeLeadSearchClient(leads))

    result = await service.find_leads(industry="Retail", geography="UAE", limit=2)

    assert len(result) == 2
    assert result == leads[:2]


async def test_find_leads_passes_exclude_terms_through_to_the_search_client() -> None:
    search_client = FakeLeadSearchClient([])
    service, _ = _service(lead_search_client=search_client)

    await service.find_leads(
        industry="Retail", geography="UAE", limit=2, exclude_terms=("construction",)
    )

    assert search_client.calls == [("Retail", "UAE", ("construction",))]


async def test_open_confirm_form_delegates_to_the_seller_draft_port() -> None:
    service, draft_port = _service()
    draft = SellerDraft(org_name="Acme Co", values={}, source_urls=())

    await service.open_confirm_form(
        trigger_id="trigger.1", draft=draft, channel_id="C1", requested_by="U1"
    )

    assert draft_port.calls == [draft]


async def test_open_review_form_loads_the_stored_draft() -> None:
    store = FakeReviewStore()
    draft = SellerDraft(org_name="Acme Co", source_place_id="p1")
    store.drafts["p1"] = draft
    service, draft_port = _service(store=store)

    await service.open_review_form(
        trigger_id="trigger.1", review_id="p1", channel_id="C1", requested_by="U1"
    )

    assert draft_port.calls == [draft]


async def test_open_review_form_raises_for_an_unknown_review() -> None:
    service, draft_port = _service()

    with pytest.raises(NotFoundError):
        await service.open_review_form(
            trigger_id="trigger.1", review_id="nope", channel_id="C1", requested_by="U1"
        )
    assert draft_port.calls == []
