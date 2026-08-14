"""Orchestrates the Firecrawl fallback: reads the run's persisted
requirement profile, extracts a query, calls `FirecrawlClient`. Never
touches Slack or persists anything — the leads it returns are ephemeral,
shown once and discarded (§ persistence decision: a web-sourced lead has no
`organizations`/`seller_roles` row, so it can't satisfy `match_results`'
FK constraints without a schema change nobody asked for).
"""

import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.modules.matching.domain.scoring import CRITERION_REGISTRY, normalize_criterion
from app.modules.matching.infrastructure.repositories import MatchResultRepository
from app.modules.web_search.domain.firecrawl_client import FirecrawlClient, WebSourcedLead


def _extract_query_terms(profile: dict) -> tuple[str, str]:
    """Returns `(industry, geography)`, preferring a `sector`/`geography`
    hard requirement or soft preference (matching the scoring engine's own
    canonical criterion names) and falling back to the free-text
    `ideal_target_description`/`strategic_thesis` when neither is present —
    never an empty query.
    """
    requirements = [*profile.get("hard_requirements", []), *profile.get("soft_preferences", [])]

    def _value_for(canonical: str) -> str | None:
        synonyms = CRITERION_REGISTRY[canonical].synonyms
        for requirement in requirements:
            if normalize_criterion(requirement.get("criterion", "")) in synonyms:
                value = requirement.get("value")
                if value:
                    return value
        return None

    industry = _value_for("sector")
    geography = _value_for("geography")

    if industry and geography:
        return industry, geography

    fallback = profile.get("ideal_target_description") or profile.get("strategic_thesis") or ""
    return industry or fallback, geography or ""


class WebLeadSearchService:
    def __init__(self, sessionmaker: async_sessionmaker, firecrawl_client: FirecrawlClient) -> None:
        self._sessionmaker = sessionmaker
        self._client = firecrawl_client

    async def search(self, run_id: uuid.UUID, *, limit: int = 3) -> list[WebSourcedLead]:
        async with self._sessionmaker() as session:
            run = await MatchResultRepository(session).get_run(run_id)

        if run is None or not run.requirement_profile:
            return []

        industry, geography = _extract_query_terms(run.requirement_profile)
        if not industry and not geography:
            return []

        return await self._client.find_potential_sellers(
            industry=industry, geography=geography, limit=limit
        )
