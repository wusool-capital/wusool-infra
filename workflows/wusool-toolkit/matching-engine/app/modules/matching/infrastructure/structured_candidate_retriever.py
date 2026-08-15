"""The Branch 1 `CandidateRetriever` (§35) — loads sellers, applies the
Stage 1 structured filter. Branch 2's `HybridCandidateRetriever` (semantic
retrieval) implements the same Protocol without changing anything upstream.

Owns a `sessionmaker`, not a bound repository/session — like
`RunBuyerSellerMatchUseCase`, it opens its own short-lived session per call
rather than depending on the caller to manage one for it.
"""

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.modules.buyers.domain.value_objects import BuyerContext
from app.modules.matching.domain.candidate_retriever import CandidateBatch, CandidateRetriever
from app.modules.matching.domain.scoring import apply_structured_filters
from app.modules.requirements.domain.value_objects import RequirementProfile
from app.modules.sellers.application.mappers import to_seller_candidate
from app.modules.sellers.infrastructure.repositories import SellerRepository


class StructuredCandidateRetriever(CandidateRetriever):
    def __init__(self, sessionmaker: async_sessionmaker) -> None:
        self._sessionmaker = sessionmaker

    async def get_candidates(
        self, buyer: BuyerContext, profile: RequirementProfile
    ) -> CandidateBatch:
        async with self._sessionmaker() as session:
            roles = await SellerRepository(session).get_eligible_sellers(limit=1000)
            candidates = [to_seller_candidate(role) for role in roles]
        passed, filters_skipped = apply_structured_filters(profile, candidates)
        return CandidateBatch(
            passed=passed, filters_skipped=filters_skipped, considered=len(candidates)
        )
