"""`discover_and_create` — CRM pre-filter classification, refill after
exclusions, the per-day cap, bounded concurrency, and failure isolation."""

import pytest

from app.modules.discovery.application.base import CreationPolicy
from app.modules.discovery.application.service import DiscoveryService
from app.modules.discovery.domain.crm import CrmMatch, CrmMatchKind
from app.modules.discovery.domain.leads import DiscoveredLead
from app.modules.discovery.tests.fakes.ports import (
    FakeLeadSearchClient,
    FakeSellerDraftPort,
    FakeSellerWriterPort,
)
from app.modules.utilities import FixedWindowRateLimiter


def _leads(n: int) -> list[DiscoveredLead]:
    return [
        DiscoveredLead(name=f"Lead {i}", source_url=f"https://maps.example/{i}", place_id=f"p{i}")
        for i in range(n)
    ]


def _service(
    *,
    leads: list[DiscoveredLead],
    writer: FakeSellerWriterPort | None = None,
    client: FakeLeadSearchClient | None = None,
    cap: int = 10,
    lead_limit: int = 5,
    concurrency: int = 2,
) -> tuple[DiscoveryService, FakeSellerWriterPort]:
    writer = writer or FakeSellerWriterPort()
    service = DiscoveryService(
        lead_search_client=client or FakeLeadSearchClient(leads),
        seller_draft_port=FakeSellerDraftPort(),
        seller_writer_port=writer,
        search_limiter=FixedWindowRateLimiter(limit=cap),
        policy=CreationPolicy(
            lead_limit=lead_limit, enrichment_concurrency=concurrency, enrichment_budget_s=30.0
        ),
    )
    return service, writer


async def _run(service: DiscoveryService, key: str = "buyer-1"):
    return await service.discover_and_create(industry="Retail", geography="UAE", quota_key=key)


async def test_disabled_without_a_search_client() -> None:
    service = DiscoveryService(
        lead_search_client=None,
        seller_draft_port=FakeSellerDraftPort(),
        seller_writer_port=FakeSellerWriterPort(),
        search_limiter=FixedWindowRateLimiter(limit=10),
        policy=CreationPolicy(lead_limit=5, enrichment_concurrency=2, enrichment_budget_s=30.0),
    )

    assert (await _run(service)).status == "disabled"


async def test_new_leads_are_created_up_to_the_limit() -> None:
    service, writer = _service(leads=_leads(8))

    outcome = await _run(service)

    assert outcome.status == "ok"
    assert len(outcome.created) == 5
    assert [d.org_name for d in writer.created] == [f"Lead {i}" for i in range(5)]
    assert writer.created[0].source_place_id == "p0"


async def test_exact_matches_are_skipped_and_their_slots_refilled() -> None:
    exact = {
        "Lead 0": CrmMatch(kind=CrmMatchKind.PLACE_ID, org_attio_id="a"),
        "Lead 1": CrmMatch(kind=CrmMatchKind.DOMAIN, org_attio_id="b"),
    }
    service, writer = _service(leads=_leads(8), writer=FakeSellerWriterPort(matches=exact))

    outcome = await _run(service)

    assert outcome.already_in_crm == 2
    assert [c.org_name for c in outcome.created] == [f"Lead {i}" for i in range(2, 7)]
    assert len(writer.created) == 5


async def test_a_fuzzy_match_is_flagged_not_created() -> None:
    fuzzy = {"Lead 1": CrmMatch(kind=CrmMatchKind.FUZZY_NAME, org_name="Lead One Holdings")}
    service, writer = _service(leads=_leads(3), writer=FakeSellerWriterPort(matches=fuzzy))

    outcome = await _run(service)

    assert [d.lead.name for d in outcome.possible_duplicates] == ["Lead 1"]
    assert outcome.possible_duplicates[0].existing_org_name == "Lead One Holdings"
    assert [d.org_name for d in writer.created] == ["Lead 0", "Lead 2"]


async def test_possible_duplicates_use_up_slots() -> None:
    fuzzy = {f"Lead {i}": CrmMatch(kind=CrmMatchKind.FUZZY_NAME, org_name="X") for i in range(2)}
    service, writer = _service(
        leads=_leads(10), writer=FakeSellerWriterPort(matches=fuzzy), lead_limit=3
    )

    outcome = await _run(service)

    assert len(outcome.possible_duplicates) == 2
    assert len(outcome.created) == 1


async def test_the_search_asks_for_a_wide_pool_before_prefiltering() -> None:
    client = FakeLeadSearchClient(_leads(3))
    service, _ = _service(leads=[], client=client)

    await _run(service)

    assert client.calls  # searched once, regardless of the 5-lead limit


async def test_daily_cap_blocks_the_search_per_buyer() -> None:
    client = FakeLeadSearchClient(_leads(2))
    service, _ = _service(leads=[], client=client, cap=1)

    first = await _run(service, "buyer-1")
    second = await _run(service, "buyer-1")
    other_buyer = await _run(service, "buyer-2")

    assert first.status == "ok"
    assert second.status == "daily_cap_reached"
    assert other_buyer.status == "ok"
    assert len(client.calls) == 2


async def test_one_failed_write_does_not_abort_the_batch() -> None:
    writer = FakeSellerWriterPort(fail_names=frozenset({"Lead 1"}))
    service, _ = _service(leads=_leads(3), writer=writer)

    outcome = await _run(service)

    assert [f.lead.name for f in outcome.failed] == ["Lead 1"]
    assert outcome.failed[0].reason == "attio down"
    assert outcome.failed[0].landed == ("organization created in Attio",)
    assert {c.org_name for c in outcome.created} == {"Lead 0", "Lead 2"}


async def test_an_unverified_lead_is_returned_for_review_not_created() -> None:
    writer = FakeSellerWriterPort(review_names=frozenset({"Lead 1"}))
    service, _ = _service(leads=_leads(3), writer=writer)

    outcome = await _run(service)

    assert [u.draft.org_name for u in outcome.needs_review] == ["Lead 1"]
    assert {c.org_name for c in outcome.created} == {"Lead 0", "Lead 2"}
    assert outcome.failed == ()


async def test_creation_concurrency_is_bounded() -> None:
    writer = FakeSellerWriterPort(create_delay_s=0.01)
    service, _ = _service(leads=_leads(5), writer=writer, concurrency=2)

    await _run(service)

    assert writer.max_in_flight == 2


async def test_a_search_that_finds_nothing_does_not_use_up_a_daily_run() -> None:
    client = FakeLeadSearchClient([])
    service, _ = _service(leads=[], client=client, cap=1)

    await _run(service)
    second = await _run(service)

    assert second.status == "ok"
    assert len(client.calls) == 2


async def test_a_search_that_raises_does_not_use_up_a_daily_run() -> None:
    class _Boom(FakeLeadSearchClient):
        async def find_potential_sellers(self, **kwargs):  # type: ignore[override]
            raise RuntimeError("places down")

    service, _ = _service(leads=[], client=_Boom([]), cap=1)

    with pytest.raises(RuntimeError):
        await _run(service)
    with pytest.raises(RuntimeError):
        await _run(service)  # the cap didn't block the second attempt
