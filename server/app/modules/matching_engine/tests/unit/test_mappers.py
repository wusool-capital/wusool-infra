"""Mapper-configuration test: catches a typo'd cross-module string
forward-reference (e.g. `Mapped["BuyeRole"]`) or a bad `foreign_keys=`
argument across every model. Needs no database connection — runs in the
default no-tunnel suite. Run this before anything in tests/integration/.
"""

from sqlalchemy.orm import configure_mappers

from app.modules.matching_engine.persistence.database import import_all_models


def test_all_models_configure_without_a_database() -> None:
    import_all_models()
    configure_mappers()


def test_search_phrase_round_trips_and_defaults_for_old_profiles() -> None:
    from app.modules.matching_engine.domain.requirements import RequirementProfile
    from app.modules.matching_engine.persistence.mappers import _profile_from_dict, profile_to_dict

    profile = RequirementProfile(
        hard_requirements=[],
        soft_preferences=[],
        strategic_thesis=None,
        ideal_target_description=None,
        scoring_rubric={},
        data_confidence=1.0,
        generated_by_model="m",
        version=1,
        search_phrase="AI wealth management",
    )
    stored = profile_to_dict(profile)

    assert _profile_from_dict(stored, version=1).search_phrase == "AI wealth management"
    del stored["search_phrase"]
    assert _profile_from_dict(stored, version=1).search_phrase is None
