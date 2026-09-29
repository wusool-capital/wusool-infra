"""The advisor's typed context outranks stored CRM data for the same
criterion — including in the SQL narrowing, or a US-stored buyer would never
see the Egyptian sellers the advisor asked for.
"""

from dataclasses import replace

import pytest
from pydantic import ValidationError

from app.modules.discrepancies.application.check import DiscrepancyCheckResult
from app.modules.discrepancies.domain.criteria import Discrepancy, DiscrepancyReport
from app.modules.discrepancies.domain.vocabulary import Criterion
from app.modules.matching_engine.api.slack.schemas import RunAnywayValue
from app.modules.matching_engine.api.slack.views.buyer_selection import _MAX_CONTEXT_CHARS
from app.modules.matching_engine.api.slack.views.discrepancy_gate import (
    build_discrepancy_gate_blocks,
)
from app.modules.matching_engine.domain.matching.narrowing import CandidateNarrowing
from app.modules.matching_engine.domain.matching.overrides import apply_advisor_overrides
from app.modules.matching_engine.domain.requirements import (
    HardRequirement,
    RequirementProfile,
    RequirementSource,
)
from app.modules.matching_engine.tests.unit.test_candidate_narrowing import _buyer


def _hard(criterion: str, value: str, source: RequirementSource) -> HardRequirement:
    return HardRequirement(
        criterion, value, source, "high", source in {"crm_field", "advisor_context"}
    )


def _profile(*hard: HardRequirement) -> RequirementProfile:
    return RequirementProfile(list(hard), [], None, None, {}, 0.8, "model", 1)


def test_advisor_geography_replaces_the_conflicting_crm_requirement() -> None:
    profile = _profile(
        _hard("geography", "United States", "crm_field"),
        _hard("geography", "Egypt", "advisor_context"),
        _hard("ebitda", "USD 2M", "crm_field"),
    )

    result = apply_advisor_overrides(profile)

    assert [(h.criterion, h.value) for h in result.hard_requirements] == [
        ("geography", "Egypt"),
        ("ebitda", "USD 2M"),
    ]


def test_synonym_criterion_names_are_recognised_as_the_same_criterion() -> None:
    profile = _profile(
        _hard("geographic_focus", "United States", "crm_field"),
        _hard("region", "Egypt", "advisor_context"),
    )

    assert [h.value for h in apply_advisor_overrides(profile).hard_requirements] == ["Egypt"]


def test_crm_requirements_are_kept_when_the_advisor_did_not_restate_them() -> None:
    profile = _profile(
        _hard("geography", "United States", "crm_field"),
        _hard("ebitda", "USD 500K", "advisor_context"),
    )

    assert apply_advisor_overrides(profile) == profile


def test_advisor_geography_replaces_the_stored_geography_in_the_narrowing() -> None:
    buyer = replace(_buyer(), target_country=["United States"])
    profile = _profile(_hard("geography", "Egypt", "advisor_context"))

    narrowing = CandidateNarrowing.from_buyer(buyer, profile)

    assert narrowing.countries >= {"egypt"}
    assert "united states" not in narrowing.countries


def test_advisor_region_is_resolved_as_a_region_not_a_country() -> None:
    profile = _profile(_hard("geography", "GCC", "advisor_context"))

    narrowing = CandidateNarrowing.from_buyer(_buyer(target_country=["Egypt"]), profile)

    assert "saudi arabia" in narrowing.countries
    assert "egypt" not in narrowing.countries


def test_advisor_sector_replaces_the_stored_vertical_in_the_narrowing() -> None:
    profile = _profile(_hard("sector", "AI", "advisor_context"))

    narrowing = CandidateNarrowing.from_buyer(_buyer(target_vertical="Pharma Tech"), profile)

    assert narrowing.vertical == "ai"


def test_narrowing_ignores_unconfirmed_advisor_lookalikes() -> None:
    llm_guess = HardRequirement("geography", "Egypt", "llm_extracted", "low", False)
    buyer = _buyer(target_country=["United States"])

    narrowing = CandidateNarrowing.from_buyer(buyer, _profile(llm_guess))

    assert narrowing.countries >= {"united states"}


def test_run_anyway_button_carries_the_advisor_context() -> None:
    conflict = Discrepancy(Criterion.GEOGRAPHY, "conflict", stored="United States", stated="Egypt")
    result = DiscrepancyCheckResult(
        report=DiscrepancyReport(buyer_role_id="buyer-1", conflicts=(conflict,), missing=()),
        message="Heads up.",
    )

    blocks = build_discrepancy_gate_blocks("buyer-1", result, "I want Egypt")

    button = blocks[-1].elements[0]
    assert RunAnywayValue.model_validate_json(button.value) == RunAnywayValue(
        buyer_role_id="buyer-1", advisor_context="I want Egypt"
    )


def test_worst_case_context_still_fits_a_slack_button_value() -> None:
    worst_case = '"\n' * (_MAX_CONTEXT_CHARS // 2)
    value = RunAnywayValue(buyer_role_id="x" * 36, advisor_context=worst_case).model_dump_json()

    assert len(value) <= 2000


def test_a_legacy_bare_id_button_value_is_not_valid_json_payload() -> None:
    with pytest.raises(ValidationError):
        RunAnywayValue.model_validate_json("11111111-1111-1111-1111-111111111111")
