"""The §35 future-proofing seam: Branch 2 can add a `HybridCandidateRetriever`
(structured filtering + semantic retrieval) implementing this same Protocol,
without changing anything above it (the orchestrator, scoring, reasoning).
Branch 1 has exactly one implementation: `StructuredCandidateRetriever`.
"""

from dataclasses import dataclass
from typing import Protocol

from app.modules.buyers.domain.value_objects import BuyerContext
from app.modules.requirements.domain.value_objects import RequirementProfile
from app.modules.sellers.domain.value_objects import SellerCandidate


@dataclass(frozen=True)
class CandidateBatch:
    passed: list[SellerCandidate]
    filters_skipped: list[dict]
    considered: int


class CandidateRetriever(Protocol):
    async def get_candidates(
        self, buyer: BuyerContext, profile: RequirementProfile
    ) -> CandidateBatch: ...
