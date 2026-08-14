"""Buyer requirement extraction (§5, §7): strict validation, one bounded
repair retry, fail-closed. Mocked Bedrock — never calls AWS.
"""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.modules.buyers.domain.value_objects import BuyerContext
from app.modules.llm.domain.bedrock_client import InferenceConfig
from app.modules.requirements.application.extraction_service import (
    BuyerRequirementExtractionService,
    RequirementExtractionError,
)
from app.shared.types import MeetingNote
from tests.fakes.bedrock import FakeBedrockClient

VALID_RESPONSE = {
    "hard_requirements": [
        {
            "criterion": "minimum_revenue",
            "value": "50M",
            "source": "llm_extracted",
            "confidence": "low",
            "human_confirmed": False,
        }
    ],
    "soft_preferences": [],
    "strategic_thesis": "Roll-up of regional fintechs",
    "ideal_target_description": "Profitable fintech, AED 50M+ revenue",
    "scoring_rubric": {"minimum_revenue": 1.0},
    "data_confidence": 0.6,
}

MALFORMED_RESPONSE = {"hard_requirements": "not a list"}


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
        investment_strategy="We acquire profitable fintechs with AED 50M+ revenue in the GCC.",
        notes=None,
        contact_person_id=None,
    )


def _inference_config() -> InferenceConfig:
    return InferenceConfig(temperature=0.2, max_tokens=4096, top_p=0.9)


async def test_valid_response_produces_requirement_profile() -> None:
    fake = FakeBedrockClient(structured_responses=[VALID_RESPONSE])
    service = BuyerRequirementExtractionService(
        fake, model_id="test-model", inference_config=_inference_config()
    )

    profile = await service.extract(_buyer(), next_version=1)

    assert profile.version == 1
    assert profile.generated_by_model == "test-model"
    assert profile.hard_requirements[0].criterion == "minimum_revenue"
    assert profile.hard_requirements[0].human_confirmed is False
    assert len(fake.structured_calls) == 1


async def test_malformed_response_triggers_one_repair_retry_then_succeeds() -> None:
    fake = FakeBedrockClient(structured_responses=[MALFORMED_RESPONSE, VALID_RESPONSE])
    service = BuyerRequirementExtractionService(
        fake, model_id="test-model", inference_config=_inference_config()
    )

    profile = await service.extract(_buyer(), next_version=2)

    assert profile.version == 2
    assert len(fake.structured_calls) == 2  # original + one repair attempt


async def test_still_malformed_after_repair_fails_closed() -> None:
    """§7/§8: never fabricate output — fail the run cleanly."""
    fake = FakeBedrockClient(structured_responses=[MALFORMED_RESPONSE, MALFORMED_RESPONSE])
    service = BuyerRequirementExtractionService(
        fake, model_id="test-model", inference_config=_inference_config()
    )

    with pytest.raises(RequirementExtractionError):
        await service.extract(_buyer(), next_version=1)

    assert len(fake.structured_calls) == 2  # no infinite retries


async def test_prompt_unchanged_when_no_meeting_notes() -> None:
    """Regression guard for the "omit entirely when empty" rule."""
    fake = FakeBedrockClient(structured_responses=[VALID_RESPONSE])
    service = BuyerRequirementExtractionService(
        fake, model_id="test-model", inference_config=_inference_config()
    )

    await service.extract(_buyer(), next_version=1)

    assert "Recent meeting notes" not in fake.structured_calls[0]


async def test_prompt_includes_labeled_meeting_notes_section_when_present() -> None:
    fake = FakeBedrockClient(structured_responses=[VALID_RESPONSE])
    service = BuyerRequirementExtractionService(
        fake, model_id="test-model", inference_config=_inference_config()
    )
    buyer = replace(
        _buyer(),
        meeting_notes=[
            MeetingNote(
                occurred_at=datetime(2026, 8, 1, tzinfo=UTC),
                title="Mandate call",
                summary="Looking for platform plays in special education centers.",
                truncated=False,
            )
        ],
    )

    await service.extract(buyer, next_version=1)
    prompt = fake.structured_calls[0]

    assert "Recent meeting notes" in prompt
    assert "special education centers" in prompt
    # The section must appear after the "don't invent a criterion" guardrail.
    assert prompt.index("fold it into") < prompt.index("Recent meeting notes")
    assert "human_confirmed: false" in prompt
    assert "Acme Capital" in prompt.split("Recent meeting notes")[1]
