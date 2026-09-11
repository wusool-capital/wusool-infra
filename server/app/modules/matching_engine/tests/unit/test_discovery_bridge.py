"""`extract_query_terms` — the pure criterion-extraction logic behind the
`discovery` web-fallback query. No database, no Firecrawl.

Ported from the deleted `test_lead_search_service.py` (covered
`web_search.py::_extract_query_terms` before that module was deleted and
this logic moved to `discovery_bridge.py`) — same behavior, new home.
"""

from app.modules.matching_engine.application.discovery_bridge import extract_query_terms
from app.modules.matching_engine.domain.requirements import (
    HardRequirement,
    RequirementProfile,
    SoftPreference,
)


def _profile(**overrides: object) -> RequirementProfile:
    base: dict = {
        "hard_requirements": [],
        "soft_preferences": [],
        "strategic_thesis": None,
        "ideal_target_description": None,
        "scoring_rubric": {},
        "data_confidence": 1.0,
        "generated_by_model": "test-model",
        "version": 1,
    }
    base.update(overrides)
    return RequirementProfile(**base)


def _hard(criterion: str, value: str) -> HardRequirement:
    return HardRequirement(
        criterion=criterion,
        value=value,
        source="crm_field",
        confidence="high",
        human_confirmed=True,
    )


def _soft(criterion: str, value: str, weight: float = 0.5) -> SoftPreference:
    return SoftPreference(
        criterion=criterion, value=value, weight=weight, source="crm_field", confidence="high"
    )


def test_prefers_sector_and_geography_hard_requirements() -> None:
    profile = _profile(
        hard_requirements=[
            _hard("sector", "healthcare"),
            _hard("geography", "Saudi Arabia"),
        ]
    )

    industry, geography, exclude_terms = extract_query_terms(profile)

    assert industry == "healthcare"
    assert geography == "Saudi Arabia"
    assert exclude_terms == ()


def test_matches_criterion_synonyms() -> None:
    """`industry` is a recognized synonym for the `sector` canonical name,
    `geographic_focus` for `geography` — same registry scoring.py uses."""
    profile = _profile(
        hard_requirements=[_hard("industry", "fintech")],
        soft_preferences=[_soft("geographic_focus", "UAE")],
    )

    industry, geography, _ = extract_query_terms(profile)

    assert industry == "fintech"
    assert geography == "UAE"


def test_falls_back_to_free_text_when_criteria_missing() -> None:
    profile = _profile(ideal_target_description="A profitable KSA healthcare operator.")

    industry, geography, _ = extract_query_terms(profile)

    assert industry == "A profitable KSA healthcare operator."
    assert geography == ""


def test_folds_client_type_into_industry_when_sector_and_geography_known() -> None:
    profile = _profile(
        hard_requirements=[
            _hard("sector", "healthcare"),
            _hard("geography", "UAE"),
            _hard("client_type", "SMB"),
        ]
    )

    industry, geography, _ = extract_query_terms(profile)

    assert industry == "healthcare SMB"
    assert geography == "UAE"


def test_client_type_is_not_folded_into_the_free_text_fallback() -> None:
    """`client_type` only refines a real `sector` value — folding it into a
    free-text fallback (already unstructured prose) would just be noise."""
    profile = _profile(
        hard_requirements=[_hard("client_type", "SMB")],
        ideal_target_description="A profitable KSA healthcare operator.",
    )

    industry, _, _ = extract_query_terms(profile)

    assert industry == "A profitable KSA healthcare operator."


def test_collects_every_sector_exclusion_value_as_exclude_terms() -> None:
    profile = _profile(
        hard_requirements=[
            _hard("sector", "healthcare"),
            _hard("geography", "UAE"),
            _hard("sector_exclusion", "construction"),
        ],
        soft_preferences=[_soft("excluded_sector", "real estate")],
    )

    _, _, exclude_terms = extract_query_terms(profile)

    assert exclude_terms == ("construction", "real estate")


def test_exclude_terms_is_empty_when_no_sector_exclusion_present() -> None:
    profile = _profile(hard_requirements=[_hard("sector", "healthcare"), _hard("geography", "UAE")])

    _, _, exclude_terms = extract_query_terms(profile)

    assert exclude_terms == ()
