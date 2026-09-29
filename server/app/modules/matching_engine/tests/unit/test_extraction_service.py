"""Buyer requirement extraction (§5, §7): strict validation, one bounded
repair retry, fail-closed. Mocked Bedrock — never calls AWS.
"""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.modules.matching_engine.application.ports.llm import InferenceConfig
from app.modules.matching_engine.application.requirements import (
    BuyerRequirementExtractionService,
    RequirementExtractionError,
)
from app.modules.matching_engine.domain.buyers import BuyerContext
from app.modules.matching_engine.domain.meetings import MeetingNote
from app.modules.matching_engine.domain.requirements import AdvisorLimits
from app.modules.matching_engine.tests.fakes.bedrock import FakeBedrockClient

VALID_RESPONSE = {
    "hard_requirements": [
        {
            "criterion": "minimum_revenue",
            "value": "USD 50M",
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


async def test_non_crm_requirement_cannot_claim_human_confirmation() -> None:
    response = {
        **VALID_RESPONSE,
        "hard_requirements": [
            {
                "criterion": "minimum_revenue",
                "value": "USD 50M",
                "source": "llm_extracted",
                "confidence": "high",
                "human_confirmed": True,
            }
        ],
    }
    fake = FakeBedrockClient(structured_responses=[response])
    service = BuyerRequirementExtractionService(
        fake, model_id="test-model", inference_config=_inference_config()
    )

    profile = await service.extract(_buyer(), next_version=1)

    assert profile.hard_requirements[0].human_confirmed is False


async def test_non_usd_monetary_requirement_retries_then_fails_closed() -> None:
    invalid = {
        **VALID_RESPONSE,
        "hard_requirements": [
            {
                "criterion": "minimum_revenue",
                "value": "AED 50M",
                "source": "llm_extracted",
                "confidence": "high",
                "human_confirmed": False,
            }
        ],
    }
    fake = FakeBedrockClient(structured_responses=[invalid, invalid])
    service = BuyerRequirementExtractionService(
        fake, model_id="test-model", inference_config=_inference_config()
    )

    with pytest.raises(RequirementExtractionError):
        await service.extract(_buyer(), next_version=1)

    assert len(fake.structured_calls) == 2


async def test_missing_monetary_value_remains_unknown() -> None:
    missing_value = {
        **VALID_RESPONSE,
        "hard_requirements": [
            {
                "criterion": "minimum_revenue",
                "value": None,
                "source": "llm_extracted",
                "confidence": "low",
                "human_confirmed": False,
            }
        ],
    }
    fake = FakeBedrockClient(structured_responses=[missing_value])
    service = BuyerRequirementExtractionService(
        fake, model_id="test-model", inference_config=_inference_config()
    )

    profile = await service.extract(_buyer(), next_version=1)

    assert profile.hard_requirements[0].value is None
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


async def test_prompt_includes_target_region_as_a_known_field() -> None:
    """The geography field used to be dropped entirely between the ORM row
    and `BuyerContext` — a buyer with a real, populated value still produced
    an unrestricted seller search, since nothing told the LLM it existed.
    The 2026-09-26 split made it two fields, so there are two ways to
    reintroduce that bug; this pins the region half.
    """
    fake = FakeBedrockClient(structured_responses=[VALID_RESPONSE])
    service = BuyerRequirementExtractionService(
        fake, model_id="test-model", inference_config=_inference_config()
    )
    buyer = replace(_buyer(), target_region=["GCC", "Global"])

    await service.extract(buyer, next_version=1)

    prompt = fake.structured_calls[0]
    known_fields_start = prompt.index("Known structured buyer fields")
    context_start = prompt.index("Additional buyer/organization context")
    assert known_fields_start < prompt.index("GCC") < context_start


async def test_prompt_never_labels_org_hq_country_as_target_geography() -> None:
    """`org_hq_country` is the buyer's own HQ, not their target market — it
    must land in the context section, never in `known_fields`, or the LLM
    could mistake "buyer is UK-based" for "buyer wants UK-based sellers"."""
    fake = FakeBedrockClient(structured_responses=[VALID_RESPONSE])
    service = BuyerRequirementExtractionService(
        fake, model_id="test-model", inference_config=_inference_config()
    )
    buyer = replace(_buyer(), org_hq_country="United Kingdom", target_region=["GCC"])

    await service.extract(buyer, next_version=1)

    prompt = fake.structured_calls[0]
    known_fields_line = next(line for line in prompt.splitlines() if "Known structured" in line)
    assert "United Kingdom" not in known_fields_line
    assert "NOT their target geography" in prompt


async def test_missing_free_text_renders_as_not_provided_not_unknown() -> None:
    """The prompt used to literally show `Unknown` for a blank
    investment_strategy/notes — Bedrock would echo that placeholder back as
    a real `strategic_thesis`/`ideal_target_description` value for a buyer
    with no free text at all. `(not provided)` reads unambiguously as "no
    data", not as content to repeat.
    """
    fake = FakeBedrockClient(structured_responses=[VALID_RESPONSE])
    service = BuyerRequirementExtractionService(
        fake, model_id="test-model", inference_config=_inference_config()
    )
    buyer = replace(_buyer(), investment_strategy=None, notes=None)

    await service.extract(buyer, next_version=1)

    prompt = fake.structured_calls[0]
    assert "(not provided)" in prompt
    assert "Unknown" not in prompt


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


async def test_prompt_includes_advisor_context_and_confirmation_rule() -> None:
    fake = FakeBedrockClient(structured_responses=[VALID_RESPONSE])
    service = BuyerRequirementExtractionService(
        fake, model_id="test-model", inference_config=_inference_config()
    )

    await service.extract(_buyer(), next_version=1, advisor_context="500K EBITDA floor")

    prompt = fake.structured_calls[0]
    assert "Advisor context" in prompt
    assert "500K EBITDA floor" in prompt
    assert "source advisor_context and human_confirmed: true" in prompt


async def test_prompt_omits_advisor_context_section_when_none_given() -> None:
    fake = FakeBedrockClient(structured_responses=[VALID_RESPONSE])
    service = BuyerRequirementExtractionService(
        fake, model_id="test-model", inference_config=_inference_config()
    )

    await service.extract(_buyer(), next_version=1)

    assert "Advisor context (typed" not in fake.structured_calls[0]


async def test_advisor_context_requirement_keeps_human_confirmed() -> None:
    response = {
        **VALID_RESPONSE,
        "hard_requirements": [
            {
                "criterion": "ebitda",
                "value": "USD 500K",
                "source": "advisor_context",
                "confidence": "high",
                "human_confirmed": True,
            },
            {
                "criterion": "minimum_revenue",
                "value": "USD 50M",
                "source": "llm_extracted",
                "confidence": "low",
                "human_confirmed": True,
            },
        ],
    }
    fake = FakeBedrockClient(structured_responses=[response])
    service = BuyerRequirementExtractionService(
        fake, model_id="test-model", inference_config=_inference_config()
    )

    profile = await service.extract(_buyer(), next_version=1, advisor_context="500K EBITDA floor")

    confirmed = {h.criterion: h.human_confirmed for h in profile.hard_requirements}
    assert confirmed == {"ebitda": True, "minimum_revenue": False}


async def test_advisor_context_source_is_downgraded_when_no_context_was_typed() -> None:
    response = {
        **VALID_RESPONSE,
        "hard_requirements": [
            {
                "criterion": "ebitda",
                "value": "USD 500K",
                "source": "advisor_context",
                "confidence": "high",
                "human_confirmed": True,
            }
        ],
    }
    fake = FakeBedrockClient(structured_responses=[response])
    service = BuyerRequirementExtractionService(
        fake, model_id="test-model", inference_config=_inference_config()
    )

    profile = await service.extract(_buyer(), next_version=1)

    (requirement,) = profile.hard_requirements
    assert (requirement.source, requirement.human_confirmed) == ("llm_extracted", False)


async def test_advisor_geography_supersedes_the_crm_geography_requirement() -> None:
    response = {
        **VALID_RESPONSE,
        "hard_requirements": [
            {
                "criterion": "geography",
                "value": "United States",
                "source": "crm_field",
                "confidence": "high",
                "human_confirmed": True,
            },
            {
                "criterion": "geography",
                "value": "Egypt",
                "source": "advisor_context",
                "confidence": "high",
                "human_confirmed": True,
            },
        ],
    }
    fake = FakeBedrockClient(structured_responses=[response])
    service = BuyerRequirementExtractionService(
        fake, model_id="test-model", inference_config=_inference_config()
    )

    profile = await service.extract(_buyer(), next_version=1, advisor_context="I want Egypt")

    assert [h.value for h in profile.hard_requirements] == ["Egypt"]
    assert "OVERRIDES any conflicting structured buyer field" in fake.structured_calls[0]


def _service(response: dict) -> tuple[BuyerRequirementExtractionService, FakeBedrockClient]:
    fake = FakeBedrockClient(structured_responses=[response])
    service = BuyerRequirementExtractionService(
        fake, model_id="test-model", inference_config=_inference_config()
    )
    return service, fake


async def test_advisor_limits_are_parsed_to_usd_amounts() -> None:
    limits = {"ticket_min": "USD 5M", "ticket_max": "USD 15M", "ev_ceiling": "USD 40M"}
    service, _ = _service({**VALID_RESPONSE, "advisor_limits": limits})

    profile = await service.extract(
        _buyer(), next_version=1, advisor_context="$5-15M tickets, EV cap $40M"
    )

    assert profile.advisor_limits == AdvisorLimits(5_000_000.0, 15_000_000.0, 40_000_000.0)


async def test_advisor_limits_are_ignored_when_no_context_was_typed() -> None:
    service, _ = _service({**VALID_RESPONSE, "advisor_limits": {"ticket_max": "USD 15M"}})

    profile = await service.extract(_buyer(), next_version=1)

    assert profile.advisor_limits == AdvisorLimits()


async def test_unparseable_advisor_limit_triggers_the_repair_retry() -> None:
    bad = {**VALID_RESPONSE, "advisor_limits": {"ticket_max": "about fifteen million"}}
    good = {**VALID_RESPONSE, "advisor_limits": {"ticket_max": "USD 15M"}}
    fake = FakeBedrockClient(structured_responses=[bad, good])
    service = BuyerRequirementExtractionService(
        fake, model_id="test-model", inference_config=_inference_config()
    )

    profile = await service.extract(_buyer(), next_version=1, advisor_context="up to 15M tickets")

    assert profile.advisor_limits.ticket_max == 15_000_000.0
    assert len(fake.structured_calls) == 2


@pytest.mark.parametrize(
    ("context", "expected"),
    [
        ("up to 10M", AdvisorLimits()),
        ("up to 10M revenue", AdvisorLimits()),
        ("up to 10M tickets", AdvisorLimits(ticket_max=10_000_000.0)),
        ("cheque size up to 10M", AdvisorLimits(ticket_max=10_000_000.0)),
        ("EV cap 10M", AdvisorLimits(ev_ceiling=10_000_000.0)),
    ],
)
async def test_a_limit_needs_a_keyword_in_the_advisors_own_words(
    context: str, expected: AdvisorLimits
) -> None:
    """The model may misread a bare amount; only a named measure is trusted."""
    guess = {"ticket_max": "USD 10M", "ev_ceiling": "USD 10M"}
    service, _ = _service({**VALID_RESPONSE, "advisor_limits": guess})

    profile = await service.extract(_buyer(), next_version=1, advisor_context=context)

    limits = profile.advisor_limits
    assert (limits.ticket_max, limits.ev_ceiling) == (expected.ticket_max, expected.ev_ceiling)


async def test_prompt_tells_the_model_a_bare_amount_sets_no_limit() -> None:
    service, fake = _service(VALID_RESPONSE)

    await service.extract(_buyer(), next_version=1, advisor_context="up to 10M")

    assert "sets NO limit" in fake.structured_calls[0]
