"""§31 orchestrator: `RunBuyerSellerMatchUseCase` ties buyer resolution,
requirement extraction, candidate retrieval/filtering, deterministic
scoring, Bedrock reasoning, and persistence together. Independent of Slack —
callable from a test, or from a background task dispatched by a Slack
handler, identically.

Transaction shape (§10, §18, §32): the run/header row is created and
committed in its own short transaction immediately, so it's queryable even
if everything after it fails. The requirement profile is committed once
extraction succeeds. The final candidate rows, their linked `match_scores`
rows, and the run's completion are one atomic transaction. Any failure along
the way marks the run `FAILED` with a safe error message in its own short
transaction — never left half-persisted, never reported as success.

Uses `MatchingUnitOfWorkFactory` for every transaction — `RunBuyerSellerMatchUseCase`
opens several independent short-lived ones within one method (see the
transaction-shape note above), so it needs a factory it can call repeatedly,
not a single request-scoped Unit of Work.
"""

import logging
import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

from app.modules.matching_engine.application.matching.reasoning_service import (
    MatchReasoningService,
)
from app.modules.matching_engine.application.ports.matching import CandidateRetriever
from app.modules.matching_engine.application.ports.unit_of_work import MatchingUnitOfWorkFactory
from app.modules.matching_engine.application.requirements import (
    BuyerRequirementExtractionService,
)
from app.modules.matching_engine.domain.buyers import BuyerContext
from app.modules.matching_engine.domain.matching.entities import (
    CandidateScore,
    MatchAnalysisData,
)
from app.modules.matching_engine.domain.matching.scoring import ScoringEngine, select_top_n
from app.modules.matching_engine.domain.sellers import SellerCandidate

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ShortlistedResult:
    match_result_id: str
    rank: int
    seller_role_id: str
    seller_org_name: str
    match_score: float
    data_confidence: float
    why_it_matches: str | None
    why_chosen_over_alternatives: str | None
    recommended_pitch: str | None
    risks_and_gaps: str | None


@dataclass(frozen=True)
class MatchRunResult:
    run_id: str
    status: str  # "GENERATED" | "FAILED"
    buyer_org_name: str
    results: list[ShortlistedResult] = field(default_factory=list)
    error: str | None = None


class RunBuyerSellerMatchUseCase:
    def __init__(
        self,
        uow_factory: MatchingUnitOfWorkFactory,
        *,
        extraction_service: BuyerRequirementExtractionService,
        candidate_retriever: CandidateRetriever,
        scoring_engine: ScoringEngine,
        reasoning_service: MatchReasoningService,
        top_n: int,
        enable_seller_meeting_notes: bool = False,
    ) -> None:
        self._uow_factory = uow_factory
        self._extraction_service = extraction_service
        self._candidate_retriever = candidate_retriever
        self._scoring_engine = scoring_engine
        self._reasoning_service = reasoning_service
        self._top_n = top_n
        self._enable_seller_meeting_notes = enable_seller_meeting_notes

    async def execute(self, buyer: BuyerContext, requested_by: str | None) -> MatchRunResult:
        run_id = uuid.uuid4()
        buyer_role_id = uuid.UUID(buyer.buyer_role_id)
        started_at = datetime.now(UTC)

        async with self._uow_factory() as uow:
            await uow.match_results.create_run(
                run_id=run_id,
                buyer_attio_id=buyer.org_attio_id,
                buyer_role_id=buyer_role_id,
                requested_by=requested_by,
            )

        try:
            return await self._run(run_id, buyer_role_id, buyer, requested_by, started_at)
        except Exception as exc:
            logger.warning(
                "match_run_failed run_id=%s error=%s",
                run_id,
                exc,
                extra={"run_id": str(run_id), "error": str(exc)},
            )
            async with self._uow_factory() as uow:
                await uow.match_results.complete_run(
                    run_id,
                    status="FAILED",
                    errors={"message": "matching failed before results could be generated"},
                    completed_at=datetime.now(UTC),
                )
            return MatchRunResult(
                run_id=str(run_id),
                status="FAILED",
                buyer_org_name=buyer.org_name,
                error=f"Run ID: {run_id}",
            )

    async def _run(
        self,
        run_id: uuid.UUID,
        buyer_role_id: uuid.UUID,
        buyer: BuyerContext,
        requested_by: str | None,
        started_at: datetime,
    ) -> MatchRunResult:
        async with self._uow_factory() as uow:
            latest_version = await uow.match_results.get_latest_requirement_profile_version(
                buyer_role_id
            )
        next_version = (latest_version or 0) + 1

        profile = await self._extraction_service.extract(buyer, next_version=next_version)

        async with self._uow_factory() as uow:
            await uow.match_results.update_run_progress(
                run_id,
                model_version=profile.generated_by_model,
                requirement_profile_version=profile.version,
                requirement_profile=profile,
            )

        batch = await self._candidate_retriever.get_candidates(buyer, profile)

        scored: list[tuple[SellerCandidate, CandidateScore]] = [
            (
                candidate,
                self._scoring_engine.score(
                    buyer.buyer_role_id, candidate.seller_role_id, profile, candidate
                ),
            )
            for candidate in batch.passed
        ]
        top_scores = select_top_n([s for _, s in scored], self._top_n)
        by_seller_id = {c.seller_role_id: c for c, _ in scored}
        shortlist: list[tuple[SellerCandidate, CandidateScore]] = [
            (by_seller_id[s.seller_role_id], s) for s in top_scores
        ]

        async with self._uow_factory() as uow:
            if self._enable_seller_meeting_notes:
                shortlist = [
                    (
                        replace(
                            candidate,
                            meeting_notes=await uow.meetings.get_recent_by_org(
                                candidate.org_attio_id
                            ),
                        ),
                        score,
                    )
                    for candidate, score in shortlist
                ]

            await uow.match_results.update_run_progress(
                run_id,
                candidates_considered=batch.considered,
                candidates_filtered=len(batch.passed),
                filters_skipped=batch.filters_skipped,
            )

        reasoning = await self._reasoning_service.reason(buyer, profile, shortlist)
        reasoning_by_id = {c.seller_role_id: c for c in reasoning.candidates}

        execution_duration_ms = int((datetime.now(UTC) - started_at).total_seconds() * 1000)

        async with self._uow_factory() as uow:
            score_rows = []
            for candidate, score in shortlist:
                narrative = reasoning_by_id.get(candidate.seller_role_id)
                score_rows.append(
                    {
                        "buyer_attio_id": buyer.org_attio_id,
                        "seller_attio_id": candidate.org_attio_id,
                        "score": score.overall_score,
                        "dims": {
                            "criteria": [
                                {
                                    "criterion": c.criterion,
                                    "criterion_type": c.criterion_type,
                                    "weight": c.weight,
                                    "result": c.result,
                                    "data_backing": c.data_backing,
                                }
                                for c in score.criteria
                            ]
                        },
                        "reasoning": narrative.why_it_matches if narrative else None,
                        "citations": [],
                    }
                )
            created_scores = await uow.match_scores.create_many(score_rows)

            candidate_rows = []
            for rank, ((candidate, score), score_row) in enumerate(
                zip(shortlist, created_scores, strict=True), start=1
            ):
                narrative = reasoning_by_id.get(candidate.seller_role_id)
                candidate_rows.append(
                    {
                        "run_id": run_id,
                        "buyer_attio_id": buyer.org_attio_id,
                        "buyer_role_id": buyer_role_id,
                        "rank": rank,
                        "seller_attio_id": candidate.org_attio_id,
                        "seller_role_id": uuid.UUID(candidate.seller_role_id),
                        "match_score_id": score_row.id,
                        "match_score": score.overall_score,
                        "data_confidence": score.confidence.value,
                        "why_chosen_over_alternatives": narrative.why_chosen_over_alternatives
                        if narrative
                        else None,
                        "recommended_pitch": narrative.recommended_pitch if narrative else None,
                        "risks_and_gaps": narrative.risks_and_gaps if narrative else None,
                        # §19/§23: Branch 1 presents Approve/Reject immediately
                        # alongside the result post, so a candidate enters the
                        # review state as part of finishing the run, not as a
                        # separate, later transition (which would mean another
                        # DB round trip for no product-visible difference).
                        "status": "PENDING_REVIEW",
                    }
                )
            created_candidates = await uow.match_results.create_candidates(candidate_rows)

            await uow.match_results.complete_run(
                run_id,
                status="GENERATED",
                final_candidate_ids=[str(c.seller_role_id) for c, _ in shortlist],
                execution_duration_ms=execution_duration_ms,
                completed_at=datetime.now(UTC),
            )

        results = []
        for row, (candidate, score) in zip(created_candidates, shortlist, strict=True):
            narrative = reasoning_by_id.get(candidate.seller_role_id)
            assert row.rank is not None  # every candidate row is created with a rank
            results.append(
                ShortlistedResult(
                    match_result_id=str(row.id),
                    rank=row.rank,
                    seller_role_id=candidate.seller_role_id,
                    seller_org_name=candidate.org_name,
                    match_score=score.overall_score,
                    data_confidence=score.confidence.value,
                    why_it_matches=narrative.why_it_matches if narrative else None,
                    why_chosen_over_alternatives=row.why_chosen_over_alternatives,
                    recommended_pitch=row.recommended_pitch,
                    risks_and_gaps=row.risks_and_gaps,
                )
            )

        return MatchRunResult(
            run_id=str(run_id), status="GENERATED", buyer_org_name=buyer.org_name, results=results
        )


class GetMatchAnalysisUseCase:
    """View Full Analysis (§21) — built entirely from persisted data, never
    re-running Bedrock.
    """

    def __init__(self, uow_factory: MatchingUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, run_id: uuid.UUID) -> MatchAnalysisData | None:
        async with self._uow_factory() as uow:
            run = await uow.match_results.get_run(run_id)
            if run is None:
                return None
            candidates = await uow.match_results.get_candidates(run_id)
            scores = await uow.match_results.get_scores_for_run(run_id)

        return MatchAnalysisData(run=run, candidates=candidates, scores=scores)


@dataclass(frozen=True)
class MatchResultView:
    match_result_id: str
    rank: int
    seller_org_name: str
    match_score: float
    data_confidence: float
    why_it_matches: str | None
    status: str
    approved_by: str | None
    decision: str | None


@dataclass(frozen=True)
class MatchRunView:
    run_id: str
    buyer_org_name: str
    results: list[MatchResultView]


class GetMatchRunViewUseCase:
    """Rebuilds the compact Slack result-message state from persisted data —
    used to refresh the original message in place after an Approve/Reject
    action, so a decided candidate's buttons don't keep looking clickable.
    """

    def __init__(self, uow_factory: MatchingUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, run_id: uuid.UUID) -> MatchRunView | None:
        async with self._uow_factory() as uow:
            run = await uow.match_results.get_run(run_id)
            if run is None:
                return None
            candidates = await uow.match_results.get_candidates(run_id)
            scores = await uow.match_results.get_scores_for_run(run_id)
            scores_by_seller = {s.seller_attio_id: s for s in scores}

            buyer_org_name = run.buyer_org_name or run.buyer_attio_id
            results = [
                MatchResultView(
                    match_result_id=c.id,
                    rank=c.rank if c.rank is not None else 0,
                    seller_org_name=c.seller_org_name or (c.seller_attio_id or "Unknown"),
                    match_score=c.match_score if c.match_score is not None else 0.0,
                    data_confidence=c.data_confidence if c.data_confidence is not None else 0.0,
                    why_it_matches=(
                        scores_by_seller[c.seller_attio_id].reasoning
                        if c.seller_attio_id in scores_by_seller
                        else None
                    ),
                    status=c.status,
                    approved_by=c.approved_by,
                    decision=c.decision,
                )
                for c in candidates
            ]

        return MatchRunView(run_id=run.run_id, buyer_org_name=buyer_org_name, results=results)
