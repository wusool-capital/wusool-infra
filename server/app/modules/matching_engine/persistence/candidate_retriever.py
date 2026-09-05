"""The Branch 1 `CandidateRetriever` (§35) — loads sellers, applies the
Stage 1 structured filter. Branch 2's `HybridCandidateRetriever` (semantic
retrieval) implements the same Protocol without changing anything upstream.

Owns a `sessionmaker`, not a bound repository/session — like
`MatchingMixin.run_match`, it opens its own short-lived session per call
rather than depending on the caller to manage one for it. Lives in
`persistence/`, not `providers/`, since it queries our own database, not a
third-party API — the `CandidateRetriever` Port it implements just happens
to also call a domain function (`apply_structured_filters`), which is fine:
adapters may depend on domain, domain never depends on adapters.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.matching_engine.application.ports.matching import CandidateRetriever
from app.modules.matching_engine.domain.buyers import BuyerContext
from app.modules.matching_engine.domain.matching.entities import CandidateBatch
from app.modules.matching_engine.domain.matching.scoring import apply_structured_filters
from app.modules.matching_engine.domain.requirements import RequirementProfile
from app.modules.matching_engine.persistence.repositories.sellers_repository import SellerRepository


class StructuredCandidateRetriever(CandidateRetriever):
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def get_candidates(
        self, buyer: BuyerContext, profile: RequirementProfile
    ) -> CandidateBatch:
        async with self._sessionmaker() as session:
            candidates = await SellerRepository(session).get_eligible_sellers(limit=1000)
        passed, filters_skipped = apply_structured_filters(profile, candidates)
        return CandidateBatch(
            passed=passed, filters_skipped=filters_skipped, considered=len(candidates)
        )
