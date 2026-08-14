"""`_extract_query_terms` — the pure criterion-extraction logic behind the
Firecrawl web-fallback query. No database, no Firecrawl.
"""

from app.modules.web_search.application.lead_search_service import _extract_query_terms


def _profile(**overrides: object) -> dict:
    base = {
        "hard_requirements": [],
        "soft_preferences": [],
        "ideal_target_description": None,
        "strategic_thesis": None,
    }
    base.update(overrides)
    return base


def test_prefers_sector_and_geography_hard_requirements() -> None:
    profile = _profile(
        hard_requirements=[
            {"criterion": "sector", "value": "healthcare"},
            {"criterion": "geography", "value": "Saudi Arabia"},
        ]
    )

    industry, geography = _extract_query_terms(profile)

    assert industry == "healthcare"
    assert geography == "Saudi Arabia"


def test_matches_criterion_synonyms() -> None:
    """`industry` is a recognized synonym for the `sector` canonical name,
    `geographic_focus` for `geography` — same registry scoring.py uses."""
    profile = _profile(
        hard_requirements=[{"criterion": "industry", "value": "fintech"}],
        soft_preferences=[{"criterion": "geographic_focus", "value": "UAE", "weight": 0.5}],
    )

    industry, geography = _extract_query_terms(profile)

    assert industry == "fintech"
    assert geography == "UAE"


def test_falls_back_to_free_text_when_criteria_missing() -> None:
    profile = _profile(ideal_target_description="A profitable KSA healthcare operator.")

    industry, geography = _extract_query_terms(profile)

    assert industry == "A profitable KSA healthcare operator."
    assert geography == ""
