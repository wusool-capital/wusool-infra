"""Extracts an (industry, geography) query pair from a persisted
`RequirementProfile`, for handing to `discovery.find_and_post_leads` —
moved out of the deleted `application/web_search.py`. `discovery` doesn't
know about `RequirementProfile`/`CRITERION_REGISTRY`, so this stays
matching_engine's own responsibility; searching is discovery's.
"""

from app.modules.matching_engine.domain.matching.scoring import (
    CRITERION_REGISTRY,
    normalize_criterion,
)
from app.modules.matching_engine.domain.requirements import RequirementProfile


def extract_query_terms(profile: RequirementProfile) -> tuple[str, str]:
    """Returns `(industry, geography)`, preferring a `sector`/`geography`
    hard requirement or soft preference and falling back to the free-text
    `ideal_target_description`/`strategic_thesis` when neither is present —
    never an empty query.
    """
    requirements = [*profile.hard_requirements, *profile.soft_preferences]

    def _value_for(canonical: str) -> str | None:
        synonyms = CRITERION_REGISTRY[canonical].synonyms
        for requirement in requirements:
            if normalize_criterion(requirement.criterion) in synonyms:
                if requirement.value:
                    return requirement.value
        return None

    industry = _value_for("sector")
    geography = _value_for("geography")

    if industry and geography:
        return industry, geography

    fallback = profile.ideal_target_description or profile.strategic_thesis or ""
    return industry or fallback, geography or ""
