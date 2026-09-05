"""The §35 future-proofing seam: Branch 2 can add a `HybridCandidateRetriever`
(structured filtering + semantic retrieval) implementing this same Protocol,
without changing anything above it (the orchestrator, scoring, reasoning).
Branch 1 has exactly one implementation: `StructuredCandidateRetriever`.

Also holds the Ports for `match_results`/`match_scores` persistence — used
via `MatchingUnitOfWork` (see `unit_of_work.py`), not injected standalone,
since every write use case needs several of these together within one
transaction. Every method returns a domain type (`MatchResultEntity`/
`MatchScoreResult`), never the `app.models` ORM row — mapped inside the
concrete repository.
"""

import uuid
from datetime import datetime
from typing import Protocol

from app.modules.matching_engine.domain.buyers import BuyerContext
from app.modules.matching_engine.domain.matching.entities import (
    CandidateBatch,
    FilterSkipped,
    MatchResultEntity,
    MatchScoreResult,
)
from app.modules.matching_engine.domain.requirements import RequirementProfile
from app.modules.utilities.domain.json_types import JsonObject


class CandidateRetriever(Protocol):
    async def get_candidates(
        self, buyer: BuyerContext, profile: RequirementProfile
    ) -> CandidateBatch: ...


class MatchScoreRepositoryPort(Protocol):
    async def create_many(self, rows: list[JsonObject]) -> list[MatchScoreResult]: ...
    async def get_scores_for_buyer(
        self, buyer_attio_id: str, limit: int = 50
    ) -> list[MatchScoreResult]: ...
    async def get_latest_score_for_pair(
        self, buyer_attio_id: str, seller_attio_id: str
    ) -> MatchScoreResult | None: ...


class MatchResultRepositoryPort(Protocol):
    async def create_run(
        self,
        *,
        run_id: uuid.UUID,
        buyer_attio_id: str,
        buyer_role_id: uuid.UUID,
        requested_by: str | None,
    ) -> MatchResultEntity: ...
    async def update_run_progress(
        self,
        run_id: uuid.UUID,
        *,
        model_version: str | None = None,
        requirement_profile_version: int | None = None,
        requirement_profile: RequirementProfile | None = None,
        candidates_considered: int | None = None,
        candidates_filtered: int | None = None,
        filters_skipped: list[FilterSkipped] | None = None,
    ) -> None: ...
    async def complete_run(
        self,
        run_id: uuid.UUID,
        *,
        status: str = "GENERATED",
        final_candidate_ids: list[str] | None = None,
        execution_duration_ms: int | None = None,
        errors: JsonObject | None = None,
        completed_at: datetime | None = None,
    ) -> None: ...
    async def create_candidates(self, rows: list[JsonObject]) -> list[MatchResultEntity]: ...
    async def get_run(self, run_id: uuid.UUID) -> MatchResultEntity | None: ...
    async def get_candidates(self, run_id: uuid.UUID) -> list[MatchResultEntity]: ...
    async def get_by_id(self, match_result_id: uuid.UUID) -> MatchResultEntity | None: ...
    async def get_latest_requirement_profile_version(
        self, buyer_role_id: uuid.UUID
    ) -> int | None: ...
    async def update_status(
        self,
        match_result_id: uuid.UUID,
        *,
        expected_status: str,
        status: str,
        approved_by: str | None = None,
        decision: str | None = None,
        decided_at: datetime | None = None,
        decision_notes: str | None = None,
    ) -> MatchResultEntity | None: ...
    async def get_scores_for_run(self, run_id: uuid.UUID) -> list[MatchScoreResult]: ...
