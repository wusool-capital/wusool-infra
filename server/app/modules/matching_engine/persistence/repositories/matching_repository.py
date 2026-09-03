"""Match-score and match-result persistence. `add()`/`flush()`/`execute()`
only — never `commit()` or `rollback()`; the caller (the orchestrating use
case) owns transaction boundaries, including the deliberate multi-transaction
shape `MatchResultRepository` is used with (see `create_run`'s docstring).

Implements `application.ports.matching.MatchScoreRepositoryPort`/
`MatchResultRepositoryPort` — every public method returns a domain type
(`MatchScoreResult`/`MatchResultEntity`), mapped from the ORM row here so
`app.models.MatchResult`/`MatchScore` never cross the Port boundary. Private
`_get_*_row(s)` helpers return the ORM row directly, for this class's own
internal fetch-then-mutate/fetch-then-derive-ids methods.
"""

import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import MatchResult, MatchScore
from app.modules.matching_engine.domain.matching.entities import (
    FilterSkipped,
    MatchResultEntity,
    MatchScoreResult,
)
from app.modules.matching_engine.domain.requirements import RequirementProfile
from app.modules.matching_engine.persistence.mappers import (
    filters_skipped_to_list,
    profile_to_dict,
    to_match_result_entity,
    to_match_score_result,
)


class MatchScoreRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_many(self, rows: list[dict]) -> list[MatchScoreResult]:
        """`rows` are plain kwargs dicts for `MatchScore` (buyer_attio_id,
        seller_attio_id, score, dims, reasoning, citations). Flushes only —
        does not commit.
        """
        scores = [MatchScore(**row) for row in rows]
        self._session.add_all(scores)
        await self._session.flush()
        return [to_match_score_result(score) for score in scores]

    async def get_scores_for_buyer(
        self, buyer_attio_id: str, limit: int = 50
    ) -> list[MatchScoreResult]:
        stmt = (
            select(MatchScore)
            .where(MatchScore.buyer_attio_id == buyer_attio_id)
            .order_by(MatchScore.generated_at.desc())
            .limit(limit)
        )
        scores = (await self._session.execute(stmt)).scalars().all()
        return [to_match_score_result(score) for score in scores]

    async def get_latest_score_for_pair(
        self, buyer_attio_id: str, seller_attio_id: str
    ) -> MatchScoreResult | None:
        stmt = (
            select(MatchScore)
            .where(
                MatchScore.buyer_attio_id == buyer_attio_id,
                MatchScore.seller_attio_id == seller_attio_id,
            )
            .order_by(MatchScore.generated_at.desc())
            .limit(1)
        )
        score = (await self._session.execute(stmt)).scalar_one_or_none()
        return to_match_score_result(score) if score else None


class MatchResultRepository:
    """Owns `match_results` — both the run/header row (`rank IS NULL`) and
    candidate rows (`rank IS NOT NULL`). See `models.py`'s module docstring
    for the row-kind invariant.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_run(
        self,
        *,
        run_id: uuid.UUID,
        buyer_attio_id: str,
        buyer_role_id: uuid.UUID,
        requested_by: str | None,
    ) -> MatchResultEntity:
        """Inserts the run/header row (`rank=None`). The caller must commit
        this in its own short transaction immediately after calling this —
        §18 requires the run to stay queryable even if every later stage
        fails, so this row cannot wait for the final atomic write.
        """
        run = MatchResult(
            run_id=run_id,
            buyer_attio_id=buyer_attio_id,
            buyer_role_id=buyer_role_id,
            rank=None,
            requested_by=requested_by,
        )
        self._session.add(run)
        await self._session.flush()
        return to_match_result_entity(run)

    async def _get_run_row(self, run_id: uuid.UUID) -> MatchResult | None:
        stmt = (
            select(MatchResult)
            .where(MatchResult.run_id == run_id, MatchResult.rank.is_(None))
            .options(selectinload(MatchResult.buyer_organization))
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

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
    ) -> None:
        """Partial update of the run row's audit fields as the run progresses,
        so a mid-run failure still leaves as much audit trail as possible.
        """
        run = await self._get_run_row(run_id)
        if run is None:
            return
        if model_version is not None:
            run.model_version = model_version
        if requirement_profile_version is not None:
            run.requirement_profile_version = requirement_profile_version
        if requirement_profile is not None:
            run.requirement_profile = profile_to_dict(requirement_profile)
        if candidates_considered is not None:
            run.candidates_considered = candidates_considered
        if candidates_filtered is not None:
            run.candidates_filtered = candidates_filtered
        if filters_skipped is not None:
            run.filters_skipped = filters_skipped_to_list(filters_skipped)
        await self._session.flush()

    async def complete_run(
        self,
        run_id: uuid.UUID,
        *,
        status: str = "GENERATED",
        final_candidate_ids: list[str] | None = None,
        execution_duration_ms: int | None = None,
        errors: dict | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        """Single-row UPDATE marking the run finished (successfully or not)."""
        run = await self._get_run_row(run_id)
        if run is None:
            return
        run.status = status
        run.final_candidate_ids = final_candidate_ids
        run.execution_duration_ms = execution_duration_ms
        run.errors = errors
        run.completed_at = completed_at or datetime.now(run.started_at.tzinfo)
        await self._session.flush()

    async def create_candidates(self, rows: list[dict]) -> list[MatchResultEntity]:
        """`rows` are plain kwargs dicts for candidate `MatchResult` rows
        (`rank` required, `run_id`/`buyer_attio_id`/`buyer_role_id` shared
        with the run). Flushes only — does not commit; the caller commits
        this together with the `match_scores` rows it links to, in one
        atomic transaction per §10.
        """
        candidates = [MatchResult(**row) for row in rows]
        self._session.add_all(candidates)
        await self._session.flush()
        return [to_match_result_entity(candidate) for candidate in candidates]

    async def get_run(self, run_id: uuid.UUID) -> MatchResultEntity | None:
        run = await self._get_run_row(run_id)
        return to_match_result_entity(run) if run else None

    async def _get_candidates_rows(self, run_id: uuid.UUID) -> list[MatchResult]:
        stmt = (
            select(MatchResult)
            .where(MatchResult.run_id == run_id, MatchResult.rank.is_not(None))
            .order_by(MatchResult.rank.asc())
            .options(selectinload(MatchResult.seller_organization))
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_candidates(self, run_id: uuid.UUID) -> list[MatchResultEntity]:
        candidates = await self._get_candidates_rows(run_id)
        return [to_match_result_entity(candidate) for candidate in candidates]

    async def _get_by_id_row(self, match_result_id: uuid.UUID) -> MatchResult | None:
        return await self._session.get(
            MatchResult,
            match_result_id,
            options=[selectinload(MatchResult.seller_organization)],
        )

    async def get_by_id(self, match_result_id: uuid.UUID) -> MatchResultEntity | None:
        row = await self._get_by_id_row(match_result_id)
        return to_match_result_entity(row) if row else None

    async def get_latest_requirement_profile_version(self, buyer_role_id: uuid.UUID) -> int | None:
        """Fail-closed versioning: only successful extractions set
        `requirement_profile_version` on a run row, so `MAX(...)` here
        naturally skips runs that failed before/at extraction.
        """
        stmt = select(func.max(MatchResult.requirement_profile_version)).where(
            MatchResult.buyer_role_id == buyer_role_id, MatchResult.rank.is_(None)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

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
    ) -> MatchResultEntity | None:
        """Compare-and-set a candidate status, returning None if it changed.

        The status predicate is evaluated by the database so two concurrent
        approval requests cannot both read ``PENDING_REVIEW`` and overwrite
        one another.
        """
        values = {
            "status": status,
            "approved_by": approved_by,
            "decision": decision,
            "decided_at": decided_at,
            "decision_notes": decision_notes,
        }
        values = {key: value for key, value in values.items() if value is not None}
        stmt = (
            update(MatchResult)
            .where(
                MatchResult.id == match_result_id,
                MatchResult.status == expected_status,
            )
            .values(**values)
            .returning(MatchResult.id)
        )
        updated_id = (await self._session.execute(stmt)).scalar_one_or_none()
        if updated_id is None:
            return None
        await self._session.flush()
        row = await self._get_by_id_row(updated_id)
        return to_match_result_entity(row) if row else None

    async def get_scores_for_run(self, run_id: uuid.UUID) -> list[MatchScoreResult]:
        """The linked deterministic breakdowns for this run's candidates."""
        candidates = await self._get_candidates_rows(run_id)
        score_ids = [c.match_score_id for c in candidates if c.match_score_id is not None]
        if not score_ids:
            return []
        stmt = select(MatchScore).where(MatchScore.id.in_(score_ids))
        scores = (await self._session.execute(stmt)).scalars().all()
        return [to_match_score_result(score) for score in scores]
