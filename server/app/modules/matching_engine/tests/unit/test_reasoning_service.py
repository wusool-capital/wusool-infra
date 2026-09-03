"""Stage 3 reasoning (§15): strict validation, one bounded repair retry,
fail-closed. Mocked Bedrock — never calls AWS.
"""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.modules.matching_engine.application.matching.reasoning_service import (
    MatchReasoningError,
    MatchReasoningService,
)
from app.modules.matching_engine.application.ports.llm import InferenceConfig
from app.modules.matching_engine.domain.buyers import BuyerContext
from app.modules.matching_engine.domain.matching.entities import (
    CandidateScore,
    DataConfidence,
)
from app.modules.matching_engine.domain.meetings import MeetingNote
from app.modules.matching_engine.domain.requirements import RequirementProfile
from app.modules.matching_engine.domain.sellers import SellerCandidate
from app.modules.matching_engine.tests.fakes.bedrock import FakeBedrockClient

VALID_RESPONSE = {
    "candidates": [
        {
            "seller_role_id": "seller-1",
            "why_it_matches": "Matches revenue and sector criteria.",
            "why_chosen_over_alternatives": "Highest deterministic score.",
            "recommended_pitch": "Position as a regional consolidation play.",
            "risks_and_gaps": "Geography unconfirmed.",
            "confidence_narrative": "Moderate confidence — one criterion unavailable.",
        }
    ]
}

MALFORMED_RESPONSE = {"candidates": "not a list"}


def _buyer() -> BuyerContext:
    return BuyerContext(
        buyer_role_id="buyer-1",
        org_attio_id="org-1",
        org_name="Acme Capital",
        model=None,
        mandate_status=None,
        ebitda_floor=None,
        check_size_min=None,
        check_size_max=None,
        ev_ceiling=None,
        deal_structure_tolerance=None,
        earnout_tolerance=None,
        profitable_only=None,
        investment_strategy="We acquire profitable fintechs.",
        notes=None,
        contact_person_id=None,
    )


def _profile() -> RequirementProfile:
    return RequirementProfile(
        hard_requirements=[],
        soft_preferences=[],
        strategic_thesis="Roll-up of regional fintechs",
        ideal_target_description="Profitable fintech",
        scoring_rubric={},
        data_confidence=0.6,
        generated_by_model="test-model",
        version=1,
    )


def _seller() -> SellerCandidate:
    return SellerCandidate(
        seller_role_id="seller-1",
        org_attio_id="org-seller-1",
        org_name="Fintech Co",
        outreach_tier=None,
        relationship_status=None,
        appetite_signal=None,
        readiness_score=None,
        est_revenue=None,
        est_ebitda=None,
        valuation_low=None,
        valuation_mid=None,
        valuation_high=None,
    )


def _shortlist() -> list[tuple[SellerCandidate, CandidateScore]]:
    score = CandidateScore(
        buyer_role_id="buyer-1",
        seller_role_id="seller-1",
        overall_score=82.0,
        confidence=DataConfidence(value=70.0, applicable_criteria=1, total_criteria=2),
    )
    return [(_seller(), score)]


def _inference_config() -> InferenceConfig:
    return InferenceConfig(temperature=0.2, max_tokens=4096, top_p=0.9)


async def test_valid_response_produces_reasoning_result() -> None:
    fake = FakeBedrockClient(reasoning_responses=[VALID_RESPONSE])
    service = MatchReasoningService(
        fake, model_id="test-model", inference_config=_inference_config()
    )

    result = await service.reason(_buyer(), _profile(), _shortlist())

    assert result.candidates[0].seller_role_id == "seller-1"
    assert len(fake.reasoning_calls) == 1


async def test_malformed_response_triggers_one_repair_retry_then_succeeds() -> None:
    fake = FakeBedrockClient(reasoning_responses=[MALFORMED_RESPONSE, VALID_RESPONSE])
    service = MatchReasoningService(
        fake, model_id="test-model", inference_config=_inference_config()
    )

    result = await service.reason(_buyer(), _profile(), _shortlist())

    assert result.candidates[0].seller_role_id == "seller-1"
    assert len(fake.reasoning_calls) == 2


async def test_still_malformed_after_repair_fails_closed() -> None:
    fake = FakeBedrockClient(reasoning_responses=[MALFORMED_RESPONSE, MALFORMED_RESPONSE])
    service = MatchReasoningService(
        fake, model_id="test-model", inference_config=_inference_config()
    )

    with pytest.raises(MatchReasoningError):
        await service.reason(_buyer(), _profile(), _shortlist())

    assert len(fake.reasoning_calls) == 2


async def test_prompt_omits_meeting_notes_section_when_none_present() -> None:
    fake = FakeBedrockClient(reasoning_responses=[VALID_RESPONSE])
    service = MatchReasoningService(
        fake, model_id="test-model", inference_config=_inference_config()
    )

    await service.reason(_buyer(), _profile(), _shortlist())

    assert "Recent meeting notes" not in fake.reasoning_calls[0]


async def test_prompt_includes_labeled_buyer_meeting_notes_when_present() -> None:
    fake = FakeBedrockClient(reasoning_responses=[VALID_RESPONSE])
    service = MatchReasoningService(
        fake, model_id="test-model", inference_config=_inference_config()
    )
    buyer = replace(
        _buyer(),
        meeting_notes=[
            MeetingNote(
                occurred_at=datetime(2026, 8, 1, tzinfo=UTC),
                title="Mandate call",
                summary="Ticket $20-50M, UAE and GCC platform plays.",
                truncated=False,
            )
        ],
    )

    await service.reason(buyer, _profile(), _shortlist())
    prompt = fake.reasoning_calls[0]

    assert "Recent meeting notes" in prompt
    assert "$20-50M" in prompt


async def test_candidates_context_carries_per_candidate_meeting_notes_when_enabled() -> None:
    fake = FakeBedrockClient(reasoning_responses=[VALID_RESPONSE])
    service = MatchReasoningService(
        fake, model_id="test-model", inference_config=_inference_config()
    )
    seller = replace(
        _seller(),
        meeting_notes=[
            MeetingNote(
                occurred_at=datetime(2026, 7, 1, tzinfo=UTC),
                title="Seller call",
                summary="Considering a majority sale, 70-80% stake.",
                truncated=False,
            )
        ],
    )
    score = _shortlist()[0][1]

    await service.reason(_buyer(), _profile(), [(seller, score)])
    prompt = fake.reasoning_calls[0]

    assert "70-80% stake" in prompt


async def test_candidates_context_meeting_notes_key_is_none_when_seller_has_no_notes() -> None:
    fake = FakeBedrockClient(reasoning_responses=[VALID_RESPONSE])
    service = MatchReasoningService(
        fake, model_id="test-model", inference_config=_inference_config()
    )

    await service.reason(_buyer(), _profile(), _shortlist())
    prompt = fake.reasoning_calls[0]

    assert "'meeting_notes': None" in prompt
