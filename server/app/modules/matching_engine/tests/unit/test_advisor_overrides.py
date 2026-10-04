"""The advisor's typed context outranks stored CRM data for the same
criterion — including in the SQL narrowing, or a US-stored buyer would never
see the Egyptian sellers the advisor asked for.
"""

from dataclasses import replace

import pytest
from pydantic import ValidationError

from app.modules.matching_engine.api.slack.schemas import RunAnywayValue
from app.modules.matching_engine.api.slack.views.buyer_selection import _MAX_CONTEXT_CHARS
from app.modules.matching_engine.domain.matching.narrowing import CandidateNarrowing
from app.modules.matching_engine.domain.matching.overrides import (
    UNLABELLED_AMOUNT_NOTE,
    apply_advisor_overrides,
    unlabelled_amount_note,
)
from app.modules.matching_engine.domain.matching.ticket import TicketBand
from app.modules.matching_engine.domain.requirements import (
    AdvisorLimits,
    HardRequirement,
    RequirementProfile,
    RequirementSource,
)
from app.modules.matching_engine.persistence.mappers import _profile_from_dict, profile_to_dict
from app.modules.matching_engine.tests.unit.test_candidate_narrowing import _buyer
from app.modules.utilities.domain.money import Money


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


def test_worst_case_context_still_fits_a_slack_button_value() -> None:
    worst_case = '"\n' * (_MAX_CONTEXT_CHARS // 2)
    value = RunAnywayValue(buyer_role_id="x" * 36, advisor_context=worst_case).model_dump_json()

    assert len(value) <= 2000


def test_a_legacy_bare_id_button_value_is_not_valid_json_payload() -> None:
    with pytest.raises(ValidationError):
        RunAnywayValue.model_validate_json("11111111-1111-1111-1111-111111111111")


def _with_limits(limits: AdvisorLimits) -> RequirementProfile:
    return replace(_profile(), advisor_limits=limits)


def test_advisor_ticket_band_replaces_the_stored_band_as_a_whole() -> None:
    buyer = _buyer(check_size_min=Money(5e6, "USD"), check_size_max=Money(15e6, "USD"))

    band = TicketBand.from_buyer(buyer, _with_limits(AdvisorLimits(ticket_max=8e6)))

    assert band == TicketBand(minimum=None, maximum=8e6)


def test_stored_ticket_band_is_used_when_the_advisor_stated_none() -> None:
    buyer = _buyer(check_size_min=Money(5e6, "USD"), check_size_max=Money(15e6, "USD"))

    assert TicketBand.from_buyer(buyer, _with_limits(AdvisorLimits(ev_ceiling=1e7))) == TicketBand(
        5e6, 15e6
    )


def test_advisor_ev_ceiling_replaces_the_stored_ceiling_in_the_narrowing() -> None:
    buyer = _buyer(ev_ceiling=Money(20e6, "USD"))

    narrowing = CandidateNarrowing.from_buyer(buyer, _with_limits(AdvisorLimits(ev_ceiling=50e6)))

    assert narrowing.ev_ceiling == 50e6


def test_advisor_limits_survive_persistence_and_old_profiles_load_without_them() -> None:
    profile = _with_limits(AdvisorLimits(1e6, 2e6, 3e6))
    stored = profile_to_dict(profile)

    restored = _profile_from_dict(stored, version=1)
    assert restored is not None
    assert restored.advisor_limits == profile.advisor_limits

    del stored["advisor_limits"]
    legacy = _profile_from_dict(stored, version=1)
    assert legacy is not None
    assert legacy.advisor_limits == AdvisorLimits()


@pytest.mark.parametrize("context", ["up to 10M", "budget $10M", "around USD 10M", "max 500k"])
def test_a_bare_amount_that_became_no_limit_gets_a_note(context: str) -> None:
    assert unlabelled_amount_note(context, _profile()) == UNLABELLED_AMOUNT_NOTE


def test_no_note_when_the_amount_became_a_limit() -> None:
    profile = _with_limits(AdvisorLimits(ticket_max=10e6))

    assert unlabelled_amount_note("up to 10M tickets", profile) is None


def test_no_note_when_the_amount_became_a_revenue_requirement() -> None:
    profile = _profile(_hard("revenue", "USD 20M", "advisor_context"))

    assert unlabelled_amount_note("revenue over $20M", profile) is None


def test_a_stored_crm_amount_does_not_hide_the_note() -> None:
    profile = _profile(_hard("ebitda", "USD 2M", "crm_field"))

    assert unlabelled_amount_note("up to 10M", profile) == UNLABELLED_AMOUNT_NOTE


@pytest.mark.parametrize("context", [None, "", "pharma tech only, UAE", "founded in 2024"])
def test_no_note_without_a_money_amount(context: str | None) -> None:
    assert unlabelled_amount_note(context, _profile()) is None
