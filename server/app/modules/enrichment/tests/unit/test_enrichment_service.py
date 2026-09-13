import uuid

import pytest

from app.modules.enrichment.application.ports.company_data import CompanyDataField
from app.modules.enrichment.application.service import EnrichmentService
from app.modules.enrichment.domain.research_context import CompanyContext
from app.modules.enrichment.domain.targets import EnrichmentTarget, EnrichmentTargetKind
from app.modules.enrichment.tests.fakes.company_data import FakeCompanyDataClient
from app.modules.enrichment.tests.fakes.extraction import FakeExtractionClient
from app.modules.enrichment.tests.fakes.research import FakeResearchClient
from app.modules.enrichment.tests.fakes.role_ports import FakeReviewPort, FakeRoleReader


def _service(
    *,
    current_values: dict,
    extraction_response: dict,
    research_client=None,
    company_data_clients=(),
    context: CompanyContext | None = None,
) -> tuple[EnrichmentService, FakeReviewPort]:
    review_port = FakeReviewPort()
    service = EnrichmentService(
        research_client=research_client or FakeResearchClient(),
        extraction_client=FakeExtractionClient(extraction_response),
        role_reader=FakeRoleReader(current_values, context=context),
        review_port=review_port,
        model_id="test-model",
        temperature=0.2,
        max_tokens=1024,
        min_confidence=0.5,
        company_data_clients=company_data_clients,
    )
    return service, review_port


@pytest.fixture
def target() -> EnrichmentTarget:
    return EnrichmentTarget(
        kind=EnrichmentTargetKind.SELLER,
        role_id=uuid.uuid4(),
        org_attio_id="test-org",
        org_name="Acme Co",
    )


@pytest.fixture
def buyer_target() -> EnrichmentTarget:
    return EnrichmentTarget(
        kind=EnrichmentTargetKind.BUYER,
        role_id=uuid.uuid4(),
        org_attio_id="test-buyer",
        org_name="Acme Capital",
    )


async def test_propose_skips_already_populated_fields(target: EnrichmentTarget) -> None:
    service, _ = _service(
        current_values={"est_revenue": 1_000_000},
        extraction_response={"fields": []},
    )
    proposal = await service.propose(target)
    # est_revenue is populated; the extraction client is only called for
    # fields that are still missing, so a wholly-populated set of one field
    # still returns no values (nothing missing beyond it in this fixture).
    assert proposal.values == ()


async def test_propose_drops_low_confidence_values(target: EnrichmentTarget) -> None:
    service, _ = _service(
        current_values={},
        extraction_response={
            "fields": [
                {
                    "field_name": "est_revenue",
                    "value": "5000000",
                    "source_url": "https://example.com",
                    "confidence": "low",
                    "rationale": "mentioned once",
                }
            ]
        },
    )
    proposal = await service.propose(target)
    assert proposal.values == ()


async def test_propose_keeps_high_confidence_values(target: EnrichmentTarget) -> None:
    service, _ = _service(
        current_values={},
        extraction_response={
            "fields": [
                {
                    "field_name": "est_revenue",
                    "value": "5000000",
                    "source_url": "https://example.com",
                    "confidence": "high",
                    "rationale": "stated in press release",
                }
            ]
        },
    )
    proposal = await service.propose(target)
    assert len(proposal.values) == 1
    assert proposal.values[0].field_name == "est_revenue"
    # `est_revenue` is a currency-kind field — coerced from the LLM's raw
    # string to a float before it can reach the Attio/Postgres write path.
    assert proposal.values[0].proposed == 5000000.0


async def test_propose_uses_the_structured_tier_before_the_llm_for_a_seller(
    target: EnrichmentTarget,
) -> None:
    diffbot = FakeCompanyDataClient(
        [
            CompanyDataField(
                field_name="est_revenue",
                value=5_000_000.0,
                source_url="https://acme.com",
                provider="Diffbot",
            )
        ]
    )
    service, _ = _service(
        current_values={},
        extraction_response={"fields": []},
        company_data_clients=(diffbot,),
    )

    proposal = await service.propose(target)

    assert len(proposal.values) == 1
    assert proposal.values[0].field_name == "est_revenue"
    assert proposal.values[0].proposed == 5_000_000.0
    assert proposal.values[0].confidence == 0.9
    assert "Diffbot" in proposal.values[0].rationale


async def test_propose_falls_back_to_llm_for_fields_the_structured_tier_missed(
    target: EnrichmentTarget,
) -> None:
    diffbot = FakeCompanyDataClient(
        [
            CompanyDataField(
                field_name="est_revenue",
                value=5_000_000.0,
                source_url="https://acme.com",
                provider="Diffbot",
            )
        ]
    )
    service, _ = _service(
        current_values={},
        extraction_response={
            "fields": [
                {
                    "field_name": "years_active",
                    "value": "10",
                    "source_url": "https://example.com",
                    "confidence": "high",
                    "rationale": "founded 2015",
                }
            ]
        },
        company_data_clients=(diffbot,),
    )

    proposal = await service.propose(target)

    field_names = {v.field_name for v in proposal.values}
    assert "est_revenue" in field_names  # from Diffbot
    assert "years_active" in field_names  # from the LLM fallback


async def test_propose_tries_a_second_tier_only_for_fields_the_first_tier_missed(
    target: EnrichmentTarget,
) -> None:
    diffbot = FakeCompanyDataClient(
        [
            CompanyDataField(
                field_name="est_revenue",
                value=5_000_000.0,
                source_url="https://acme.com",
                provider="Diffbot",
            )
        ]
    )
    pdl = FakeCompanyDataClient(
        [
            CompanyDataField(
                field_name="hq_country",
                value="United Arab Emirates",
                source_url="https://acme.com",
                provider="People Data Labs",
            ),
            CompanyDataField(
                field_name="est_revenue",
                value=1.0,  # would prove a bug if this ever won over Diffbot's
                source_url="https://acme.com",
                provider="People Data Labs",
            ),
        ]
    )
    service, _ = _service(
        current_values={},
        extraction_response={"fields": []},
        company_data_clients=(diffbot, pdl),
    )

    proposal = await service.propose(target)

    by_field = {v.field_name: v for v in proposal.values}
    assert by_field["est_revenue"].proposed == 5_000_000.0  # Diffbot's, not PDL's
    assert by_field["hq_country"].proposed == "United Arab Emirates"
    # PDL was never even asked for est_revenue — it had already been resolved.
    assert "est_revenue" not in dict(pdl.calls)["Acme Co"]


async def test_propose_never_tries_the_structured_tier_for_a_buyer(
    buyer_target: EnrichmentTarget,
) -> None:
    diffbot = FakeCompanyDataClient(
        [
            CompanyDataField(
                field_name="investment_strategy",
                value="should never be proposed",
                source_url="https://acme.com",
                provider="Diffbot",
            )
        ]
    )
    service, _ = _service(
        current_values={},
        extraction_response={"fields": []},
        company_data_clients=(diffbot,),
    )

    proposal = await service.propose(buyer_target)

    assert proposal.values == ()
    assert diffbot.calls == []


async def test_propose_drops_target_geography_entirely_when_no_value_matches_vocabulary(
    buyer_target: EnrichmentTarget,
) -> None:
    """Regression for the Investcorp bug: the LLM proposed regions outside
    `target_geography`'s fixed vocabulary, and the field silently vanished
    between the Slack proposal message and the edit form.
    """
    service, _ = _service(
        current_values={},
        extraction_response={
            "fields": [
                {
                    "field_name": "target_geography",
                    "value": "Gulf Cooperation Council (GCC) countries, North America, "
                    "Europe, Asia",
                    "source_url": "https://example.com",
                    "confidence": "high",
                    "rationale": "stated client base",
                }
            ]
        },
    )
    proposal = await service.propose(buyer_target)
    assert proposal.values == ()


async def test_propose_keeps_only_the_valid_members_of_a_partially_matching_target_geography(
    buyer_target: EnrichmentTarget,
) -> None:
    service, _ = _service(
        current_values={},
        extraction_response={
            "fields": [
                {
                    "field_name": "target_geography",
                    "value": "GCC-wide, North America",
                    "source_url": "https://example.com",
                    "confidence": "high",
                    "rationale": "stated client base",
                }
            ]
        },
    )
    proposal = await service.propose(buyer_target)
    assert len(proposal.values) == 1
    assert proposal.values[0].field_name == "target_geography"
    assert proposal.values[0].proposed == ["GCC-wide"]


async def test_research_query_falls_back_to_bare_name_with_no_context(
    target: EnrichmentTarget,
) -> None:
    research_client = FakeResearchClient()
    service, _ = _service(
        current_values={},
        extraction_response={"fields": []},
        research_client=research_client,
    )

    await service.propose(target)

    assert research_client.queries == ["Acme Co company profile"]


async def test_research_query_is_anchored_on_domain_when_known(
    target: EnrichmentTarget,
) -> None:
    research_client = FakeResearchClient()
    service, _ = _service(
        current_values={},
        extraction_response={"fields": []},
        research_client=research_client,
        context=CompanyContext(org_name="Acme Co", domains=("acme.com",)),
    )

    await service.propose(target)

    assert research_client.queries == ["Acme Co acme.com company profile"]


async def test_extraction_prompt_includes_known_facts_when_context_is_populated(
    target: EnrichmentTarget,
) -> None:
    extraction_client = FakeExtractionClient({"fields": []})
    service = EnrichmentService(
        research_client=FakeResearchClient(),
        extraction_client=extraction_client,
        role_reader=FakeRoleReader(
            {}, context=CompanyContext(org_name="Acme Co", hq_country="UAE")
        ),
        review_port=FakeReviewPort(),
        model_id="test-model",
        temperature=0.2,
        max_tokens=1024,
        min_confidence=0.5,
    )

    await service.propose(target)

    assert any("HQ country: UAE" in prompt for prompt in extraction_client.prompts)
