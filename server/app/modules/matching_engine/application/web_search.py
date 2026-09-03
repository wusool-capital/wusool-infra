"""Orchestrates the Firecrawl fallback: reads the run's persisted
requirement profile, extracts a query, calls `FirecrawlClient`. Never
touches Slack or persists anything — the leads it returns are ephemeral,
shown once and discarded (§ persistence decision: a web-sourced lead has no
`organizations`/`seller_roles` row, so it can't satisfy `match_results`'
FK constraints without a schema change nobody asked for).
"""

import uuid

from app.modules.matching_engine.application.ports.unit_of_work import MatchingUnitOfWorkFactory
from app.modules.matching_engine.application.ports.web_search import FirecrawlClient
from app.modules.matching_engine.domain.matching.scoring import (
    CRITERION_REGISTRY,
    normalize_criterion,
)
from app.modules.matching_engine.domain.requirements import RequirementProfile
from app.modules.matching_engine.domain.web_search import WebSourcedLead


def _extract_query_terms(profile: RequirementProfile) -> tuple[str, str]:
    """Returns `(industry, geography)`, preferring a `sector`/`geography`
    hard requirement or soft preference (matching the scoring engine's own
    canonical criterion names) and falling back to the free-text
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


class WebLeadSearchService:
    def __init__(
        self, uow_factory: MatchingUnitOfWorkFactory, firecrawl_client: FirecrawlClient
    ) -> None:
        self._uow_factory = uow_factory
        self._client = firecrawl_client

    async def search(self, run_id: uuid.UUID, *, limit: int = 3) -> list[WebSourcedLead]:
        async with self._uow_factory() as uow:
            run = await uow.match_results.get_run(run_id)

        if run is None or not run.requirement_profile:
            return []

        industry, geography = _extract_query_terms(run.requirement_profile)
        if not industry and not geography:
            return []

        return await self._client.find_potential_sellers(
            industry=industry, geography=geography, limit=limit
        )
