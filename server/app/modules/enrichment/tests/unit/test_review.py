"""Coverage for `ReviewMixin.open_review_form` — this module's only
"write-adjacent" action, which is really just a hand-off to
`EnrichmentReviewPort`.
"""

import uuid

import pytest

from app.modules.enrichment.application.service import EnrichmentService
from app.modules.enrichment.domain.field_plans import WriteTarget
from app.modules.enrichment.domain.proposals import EnrichmentProposal, ProposedFieldValue
from app.modules.enrichment.domain.targets import EnrichmentTarget, EnrichmentTargetKind
from app.modules.enrichment.tests.fakes.extraction import FakeExtractionClient
from app.modules.enrichment.tests.fakes.research import FakeResearchClient
from app.modules.enrichment.tests.fakes.role_ports import FakeReviewPort, FakeRoleReader


@pytest.fixture
def target() -> EnrichmentTarget:
    return EnrichmentTarget(
        kind=EnrichmentTargetKind.SELLER,
        role_id=uuid.uuid4(),
        org_attio_id="test-org",
        org_name="Acme Co",
    )


def _service(review_port: FakeReviewPort) -> EnrichmentService:
    return EnrichmentService(
        research_client=FakeResearchClient(),
        extraction_client=FakeExtractionClient({"fields": []}),
        role_reader=FakeRoleReader({}),
        review_port=review_port,
        model_id="test-model",
        temperature=0.2,
        max_tokens=1024,
        min_confidence=0.5,
    )


def _proposal(target: EnrichmentTarget, field_names: list[str]) -> EnrichmentProposal:
    return EnrichmentProposal(
        target=target,
        values=tuple(
            ProposedFieldValue(
                field_name=name,
                write_target=WriteTarget.SELLER_ROLE,
                current=None,
                proposed=f"value-{name}",
                source_url="https://example.com",
                confidence=0.9,
                rationale="",
            )
            for name in field_names
        ),
        generated_by_model="test-model",
    )


async def test_open_review_form_with_no_values_never_calls_the_port(
    target: EnrichmentTarget,
) -> None:
    review_port = FakeReviewPort()
    proposal = _proposal(target, [])

    await _service(review_port).open_review_form(
        trigger_id="trigger.1", proposal=proposal, channel_id="C1", requested_by="U1"
    )

    assert review_port.calls == []


async def test_open_review_form_delegates_every_value_to_the_port(
    target: EnrichmentTarget,
) -> None:
    review_port = FakeReviewPort()
    proposal = _proposal(target, ["est_revenue", "years_active"])

    await _service(review_port).open_review_form(
        trigger_id="trigger.1", proposal=proposal, channel_id="C1", requested_by="U1"
    )

    assert len(review_port.calls) == 1
    written_target, values = review_port.calls[0]
    assert written_target is target
    assert {v.field_name for v in values} == {"est_revenue", "years_active"}
