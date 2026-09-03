"""`_extract_query_terms` — the pure criterion-extraction logic behind the
Firecrawl web-fallback query. No database, no Firecrawl.
"""

from app.modules.matching_engine.application.web_search import (
    _extract_query_terms,
)
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

    industry, geography = _extract_query_terms(profile)

    assert industry == "healthcare"
    assert geography == "Saudi Arabia"


def test_matches_criterion_synonyms() -> None:
    """`industry` is a recognized synonym for the `sector` canonical name,
    `geographic_focus` for `geography` — same registry scoring.py uses."""
    profile = _profile(
        hard_requirements=[_hard("industry", "fintech")],
        soft_preferences=[_soft("geographic_focus", "UAE")],
    )

    industry, geography = _extract_query_terms(profile)

    assert industry == "fintech"
    assert geography == "UAE"


def test_falls_back_to_free_text_when_criteria_missing() -> None:
    profile = _profile(ideal_target_description="A profitable KSA healthcare operator.")

    industry, geography = _extract_query_terms(profile)

    assert industry == "A profitable KSA healthcare operator."
    assert geography == ""
