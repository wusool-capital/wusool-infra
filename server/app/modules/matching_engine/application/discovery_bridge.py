"""Extracts an (industry, geography, exclude_terms) query from a persisted
`RequirementProfile`, for handing to `discovery.find_and_post_leads` —
moved out of the deleted `application/web_search.py`. `discovery` doesn't
know about `RequirementProfile`/`CRITERION_REGISTRY`, so this stays
matching_engine's own responsibility; searching is discovery's. `discovery`
only ever receives plain strings — it has no idea `exclude_terms` came from
a `sector_exclusion` requirement, same as it has no idea `industry` came
from a `sector` one.

Only `sector`/`geography`/`client_type`/`sector_exclusion` feed the search:
`revenue`/`ebitda` floors have no textual signal in a Google Maps listing
(no financial data returned at all — see `DiscoveredLead`), and
`outreach_tier`/`relationship_status`/`appetite_signal` describe a seller's
state *within our own CRM*, which is meaningless for a lead that, by
definition, isn't in the CRM yet. Folding those in would be decorative, not
functional — left out deliberately, not missed.
"""

from app.modules.matching_engine.domain.matching.scoring import (
    CRITERION_REGISTRY,
    normalize_criterion,
)
from app.modules.matching_engine.domain.requirements import RequirementProfile


def extract_query_terms(profile: RequirementProfile) -> tuple[str, str, tuple[str, ...]]:
    """Returns `(industry, geography, exclude_terms)`. `industry`/`geography`
    prefer a hard requirement or soft preference, falling back to the
    free-text `ideal_target_description`/`strategic_thesis` when neither is
    present — never an empty query. `industry` also folds in `client_type`
    when both it and `sector` are known (e.g. "healthcare SMB"), since it's
    a genuine search-refining qualifier, not just a CRM label.
    `exclude_terms` collects every `sector_exclusion` value found (there can
    be more than one) — `discovery` filters any lead whose category/name
    matches one of them, since Google Maps' own search has no negation
    syntax reliable enough to depend on.
    """
    requirements = [*profile.hard_requirements, *profile.soft_preferences]

    def _value_for(canonical: str) -> str | None:
        synonyms = CRITERION_REGISTRY[canonical].synonyms
        for requirement in requirements:
            if normalize_criterion(requirement.criterion) in synonyms:
                if requirement.value:
                    return requirement.value
        return None

    def _values_for(canonical: str) -> tuple[str, ...]:
        synonyms = CRITERION_REGISTRY[canonical].synonyms
        return tuple(
            requirement.value
            for requirement in requirements
            if normalize_criterion(requirement.criterion) in synonyms and requirement.value
        )

    sector = _value_for("sector")
    geography = _value_for("geography")
    exclude_terms = _values_for("sector_exclusion")

    if sector and geography:
        client_type = _value_for("client_type")
        industry = f"{sector} {client_type}" if client_type else sector
        return industry, geography, exclude_terms

    fallback = profile.ideal_target_description or profile.strategic_thesis or ""
    return sector or fallback, geography or "", exclude_terms
