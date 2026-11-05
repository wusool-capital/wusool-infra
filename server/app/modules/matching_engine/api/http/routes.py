"""Thin routes over the existing matching use cases, mirroring the Slack
`/find-match` flow step by step: search → preflight → run → review → export.
Every action re-validates against the database, as the Slack handlers do.
"""

import asyncio
import csv
import io
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Annotated, get_args

from fastapi import APIRouter, Depends, Query, Response, status

from app.modules.matching_engine.api.buyers import BuyerSummary
from app.modules.matching_engine.api.dependencies import (
    find_buyer_discrepancies,
    open_matching_engine_service,
    resolve_buyer,
    resolve_buyer_by_id,
    seller_edit_port,
)
from app.modules.matching_engine.api.http.auth import CurrentUser, api_error, require_web_user
from app.modules.matching_engine.api.http.run_tracker import TrackedDiscovery, run_tracker
from app.modules.matching_engine.api.http.schemas import (
    ApiError,
    ApiErrorResponse,
    ApproveRequest,
    CandidateRead,
    ContextReadingRead,
    CriterionRead,
    DecisionResponse,
    DiscoveryRead,
    DiscrepancyRead,
    ExistingDealRead,
    ExportField,
    HardRequirementRead,
    MandateRead,
    MoneyRead,
    PreflightRequest,
    PreflightResponse,
    ResearchFieldRead,
    ResearchJobChangeRead,
    ResearchLinkedInRead,
    ResearchPostRead,
    ResearchRead,
    RunDetailResponse,
    SaveResearchRequest,
    SellerProfileRead,
    StartRunRequest,
    StartRunResponse,
)
from app.modules.matching_engine.api.http.web_research import research_seller, research_stale_after
from app.modules.matching_engine.api.http.web_runs import discover_for_web_run, execute_web_run
from app.modules.matching_engine.application.approvals import (
    InvalidTransitionError,
    MatchNotFoundError,
)
from app.modules.matching_engine.application.errors import (
    ExistingDealsFoundError,
    PartialWriteError,
)
from app.modules.matching_engine.application.ports.seller_edits import (
    SellerEditOutcome,
    SellerEditResult,
)
from app.modules.matching_engine.application.research import (
    ResearchAlreadyReviewedError,
    ResearchNotReadyError,
    ResearchSaveInProgressError,
)
from app.modules.matching_engine.application.service import MatchingEngineService
from app.modules.matching_engine.config import get_settings
from app.modules.matching_engine.domain.matching.entities import (
    MatchAnalysisData,
    MatchResultEntity,
)
from app.modules.matching_engine.domain.matching.research import ResearchRecord
from app.modules.matching_engine.domain.matching.run_state import run_state
from app.modules.matching_engine.domain.matching.scoring import needs_web_fallback
from app.modules.matching_engine.domain.requirements import RequirementProfile
from app.modules.matching_engine.domain.sellers import SellerProfile
from app.modules.utilities import Money, get_shared_task_runner

_task_runner = get_shared_task_runner()

_ERRORS: dict[int | str, dict[str, type[ApiErrorResponse]]] = {
    401: {"model": ApiErrorResponse},
    404: {"model": ApiErrorResponse},
    503: {"model": ApiErrorResponse},
}

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["find-match"],
    dependencies=[Depends(require_web_user)],
    responses=_ERRORS,
    # Short operation ids become the generated client's function and hook names.
    generate_unique_id_function=lambda route: route.name,
)


async def _service() -> AsyncIterator[MatchingEngineService]:
    async with open_matching_engine_service() as service:
        yield service


Service = Annotated[MatchingEngineService, Depends(_service)]

# Serialises the request-id check with the run it starts, so a double submit can't start two.
_start_lock = asyncio.Lock()


def _not_found(message: str) -> ApiError:
    return ApiError(code="not_found", message=message)


@router.get("/buyers", response_model=list[BuyerSummary])
async def search_buyers(q: str = Query(min_length=2, max_length=200)) -> list[BuyerSummary]:
    resolution = await resolve_buyer(q.strip())
    return resolution.candidates or []


@router.post("/buyers/{buyer_role_id}/preflight", response_model=PreflightResponse)
async def preflight(buyer_role_id: uuid.UUID, body: PreflightRequest) -> PreflightResponse:
    result = await find_buyer_discrepancies(str(buyer_role_id), body.advisor_context)
    if result is None:
        raise api_error(status.HTTP_404_NOT_FOUND, _not_found("Buyer not found."))
    context = result.context
    return PreflightResponse(
        buyer_role_id=str(buyer_role_id),
        conflicts=[
            DiscrepancyRead(criterion=d.criterion.value, stored=d.stored, stated=d.stated)
            for d in result.report.conflicts
        ],
        missing=[
            DiscrepancyRead(criterion=d.criterion.value, stored=d.stored, stated=d.stated)
            for d in result.report.missing
        ],
        context_checked=result.context_checked,
        context=ContextReadingRead(
            verticals=list(context.verticals),
            region=context.region,
            countries=list(context.countries),
            ticket_low=context.ticket_low,
            ticket_high=context.ticket_high,
            ebitda_low=context.ebitda_low,
            ebitda_high=context.ebitda_high,
            ev_ceiling=context.ev_ceiling,
            revenue_low=context.revenue_low,
            revenue_high=context.revenue_high,
            seller_status=list(context.seller_status),
        ),
    )


@router.post(
    "/match-runs",
    response_model=StartRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_match_run(
    body: StartRunRequest, service: Service, user: CurrentUser
) -> StartRunResponse:
    buyer = await resolve_buyer_by_id(str(body.buyer_role_id))
    if buyer is None:
        raise api_error(status.HTTP_404_NOT_FOUND, _not_found("Buyer not found."))
    async with _start_lock:
        if body.request_id is not None and (existing := run_tracker.started_run(body.request_id)):
            return StartRunResponse(run_id=existing)
        started = await service.start_run(buyer, user.slack_user_id)
        if body.request_id is not None:
            run_tracker.remember_start(body.request_id, started.run_id)
    # Before scheduling, so the first poll can't find it idle and call it stale.
    run_tracker.set_executing(started.run_id, True)
    _task_runner.run(
        lambda: execute_web_run(
            started,
            buyer,
            advisor_context=body.advisor_context,
            requested_by=user.slack_user_id,
        ),
        name=f"web-find-match:{started.run_id}",
    )
    return StartRunResponse(run_id=started.run_id)


@router.get("/match-runs/{run_id}", response_model=RunDetailResponse)
async def get_match_run(run_id: uuid.UUID, service: Service) -> RunDetailResponse:
    return await _run_detail(service, run_id, await _load_run(service, run_id))


@router.post(
    "/match-runs/{run_id}/discovery",
    response_model=RunDetailResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_discovery(run_id: uuid.UUID, service: Service) -> RunDetailResponse:
    """The web's "Find more sellers": a repeat call is a no-op, as in Slack."""
    analysis = await _load_run(service, run_id)
    if analysis.run.completed_at is None or analysis.run.status == "FAILED":
        raise api_error(
            status.HTTP_409_CONFLICT,
            ApiError(code="run_not_ready", message="The run hasn't completed successfully."),
        )
    detail = await _run_detail(service, run_id, analysis)
    if detail.discovery.status in ("running", "done"):
        return detail
    # Before scheduling, so a poll in the gap keeps showing the search as running.
    run_tracker.set_discovery(run_id, TrackedDiscovery(status="running"))
    _task_runner.run(lambda: discover_for_web_run(run_id), name=f"web-discover:{run_id}")
    detail.discovery = DiscoveryRead(status="running")
    return detail


@router.post(
    "/match-runs/{run_id}/candidates/{candidate_id}/approve",
    response_model=DecisionResponse,
    responses={409: {"model": ApiErrorResponse}, 502: {"model": ApiErrorResponse}},
)
async def approve_candidate(
    run_id: uuid.UUID,
    candidate_id: uuid.UUID,
    body: ApproveRequest,
    service: Service,
    user: CurrentUser,
) -> DecisionResponse:
    candidate = _require_candidate(await _load_run(service, run_id), candidate_id)
    try:
        await service.approve_match(
            candidate_id,
            user.actor,
            resolution=body.resolution,
            existing_deal_id=body.existing_deal_id,
        )
    except ExistingDealsFoundError as exc:
        raise api_error(
            status.HTTP_409_CONFLICT,
            ApiError(
                code="existing_deals",
                message="Attio already has a deal for this buyer and seller.",
                existing_deals=[
                    ExistingDealRead(
                        attio_id=d.attio_id, name=d.name, stage=d.stage, web_url=d.web_url
                    )
                    for d in exc.deals
                ],
            ),
        ) from exc
    except PartialWriteError as exc:
        logger.error(
            "match_approval_partial_write match_result_id=%s landed=%s",
            candidate_id,
            exc.landed,
            exc_info=exc.cause,
            extra={"match_result_id": str(candidate_id), "landed": exc.landed},
        )
        message = (
            "Couldn't write the deal to Attio. Nothing was saved."
            if not exc.landed
            else "Approval failed partway through. Already saved: "
            f"{'; '.join(exc.landed)}. Check the match's status before retrying."
        ) + f" ({exc.cause})"

        raise api_error(
            status.HTTP_502_BAD_GATEWAY, ApiError(code="partial_write", message=message)
        ) from exc
    except (MatchNotFoundError, InvalidTransitionError) as exc:
        raise _decision_error(exc) from exc
    decided = await _decided(service, run_id, candidate_id)
    if decided.candidate.origin == "discovery" and decided.candidate.status == "APPROVED":
        # Discovery only paid for basic enrichment; an approved seller earns the full research.
        if await _start_research(service, candidate, requested_by=user.slack_user_id):
            decided = await _decided(service, run_id, candidate_id)
    return decided


async def _start_research(
    service: MatchingEngineService, candidate: MatchResultEntity, *, requested_by: str | None
) -> bool:
    """Claims here, so the response already shows the research running."""
    role_id = candidate.seller_role_id
    match_result_id = uuid.UUID(candidate.id)
    if role_id is None or not await service.claim_research(
        match_result_id, stale_after=research_stale_after()
    ):
        return False
    _task_runner.run(
        lambda: research_seller(match_result_id, seller_role_id=role_id, requested_by=requested_by),
        name=f"web-research:{candidate.id}",
    )
    return True


def _research_target(analysis: MatchAnalysisData, candidate_id: uuid.UUID) -> MatchResultEntity:
    candidate = _require_candidate(analysis, candidate_id)
    if candidate.origin != "discovery" or candidate.status != "APPROVED":
        raise api_error(
            status.HTTP_409_CONFLICT,
            ApiError(
                code="research_not_ready",
                message="Full research is for approved sellers found outside the CRM.",
            ),
        )
    return candidate


@router.post(
    "/match-runs/{run_id}/candidates/{candidate_id}/research",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DecisionResponse,
    responses={409: {"model": ApiErrorResponse}},
)
async def start_research(
    run_id: uuid.UUID, candidate_id: uuid.UUID, service: Service, user: CurrentUser
) -> DecisionResponse:
    """Starts or retries the research; the claim makes a repeat a no-op."""
    candidate = _research_target(await _load_run(service, run_id), candidate_id)
    started = await _start_research(service, candidate, requested_by=user.slack_user_id)
    decided = await _decided(service, run_id, candidate_id)
    if not started and decided.candidate.research is None:
        # Nothing running and nothing to show: say why rather than return a silent 202.
        message = (
            "This seller has no seller profile to research."
            if candidate.seller_role_id is None
            else "This seller's stored research can't be read, so it can't be rerun."
        )
        raise api_error(
            status.HTTP_409_CONFLICT, ApiError(code="research_not_ready", message=message)
        )
    return decided


@router.post(
    "/match-runs/{run_id}/candidates/{candidate_id}/research/save",
    response_model=DecisionResponse,
    responses={
        403: {"model": ApiErrorResponse},
        409: {"model": ApiErrorResponse},
        422: {"model": ApiErrorResponse},
        502: {"model": ApiErrorResponse},
    },
)
async def save_research(
    run_id: uuid.UUID,
    candidate_id: uuid.UUID,
    body: SaveResearchRequest,
    service: Service,
    user: CurrentUser,
) -> DecisionResponse:
    if user.slack_user_id is None:
        # Attio edits are recorded under a Slack user, as `/edit-seller` records them.
        raise api_error(
            status.HTTP_403_FORBIDDEN,
            ApiError(
                code="slack_sign_in_required",
                message="Sign in with Slack to save research to Attio.",
            ),
        )
    _research_target(await _load_run(service, run_id), candidate_id)
    try:
        result = await service.save_research(
            candidate_id,
            field_names=tuple(body.fields),
            requested_by=user.slack_user_id,
            editor=seller_edit_port(),
            stale_after=research_stale_after(),
        )
    except ResearchNotReadyError as exc:
        raise api_error(
            status.HTTP_409_CONFLICT,
            ApiError(code="research_not_ready", message="The research hasn't finished yet."),
        ) from exc
    except ResearchAlreadyReviewedError as exc:
        raise api_error(
            status.HTTP_409_CONFLICT,
            ApiError(
                code="already_reviewed", message="This research was already saved or skipped."
            ),
        ) from exc
    except ResearchSaveInProgressError as exc:
        raise api_error(
            status.HTTP_409_CONFLICT,
            ApiError(code="research_busy", message="These fields are already being saved."),
        ) from exc
    if result.outcome is not SellerEditOutcome.SAVED:
        logger.warning(
            "web_research_save_failed match_result_id=%s outcome=%s message=%s",
            candidate_id,
            result.outcome,
            result.message,
        )
        raise _save_error(result)
    return await _decided(service, run_id, candidate_id)


def _save_error(result: SellerEditResult) -> Exception:
    match result.outcome:
        case SellerEditOutcome.CONFLICT:
            return api_error(
                status.HTTP_409_CONFLICT,
                ApiError(
                    code="research_conflict",
                    message="Someone filled in these fields since the research ran. "
                    "Untick them to save the rest.",
                    fields=list(result.conflicts),
                ),
            )
        case SellerEditOutcome.NOT_FOUND:
            return api_error(
                status.HTTP_404_NOT_FOUND, _not_found("This seller is no longer in the CRM.")
            )
        case SellerEditOutcome.PARTIAL:
            landed = "; ".join(result.landed)
            message = (
                f"Saving failed partway through. Already saved: {landed}. "
                if landed
                else "Couldn't write to Attio. Nothing was saved. "
            ) + f"({result.message})"
            return api_error(
                status.HTTP_502_BAD_GATEWAY, ApiError(code="partial_write", message=message)
            )
        case _:
            return api_error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                ApiError(
                    code="research_invalid",
                    message=result.message or "These values couldn't be saved.",
                ),
            )


@router.post(
    "/match-runs/{run_id}/candidates/{candidate_id}/research/skip",
    response_model=DecisionResponse,
    responses={409: {"model": ApiErrorResponse}},
)
async def skip_research(
    run_id: uuid.UUID, candidate_id: uuid.UUID, service: Service, user: CurrentUser
) -> DecisionResponse:
    _research_target(await _load_run(service, run_id), candidate_id)
    try:
        await service.skip_research(candidate_id, stale_after=research_stale_after())
    except ResearchNotReadyError as exc:
        raise api_error(
            status.HTTP_409_CONFLICT,
            ApiError(code="research_not_ready", message="The research hasn't finished yet."),
        ) from exc
    except ResearchAlreadyReviewedError as exc:
        raise api_error(
            status.HTTP_409_CONFLICT,
            ApiError(
                code="already_reviewed", message="This research was already saved or skipped."
            ),
        ) from exc
    return await _decided(service, run_id, candidate_id)


@router.post(
    "/match-runs/{run_id}/candidates/{candidate_id}/reject",
    response_model=DecisionResponse,
    responses={409: {"model": ApiErrorResponse}},
)
async def reject_candidate(
    run_id: uuid.UUID, candidate_id: uuid.UUID, service: Service, user: CurrentUser
) -> DecisionResponse:
    _require_candidate(await _load_run(service, run_id), candidate_id)
    try:
        await service.reject_match(candidate_id, user.actor)
    except (MatchNotFoundError, InvalidTransitionError) as exc:
        raise _decision_error(exc) from exc
    return await _decided(service, run_id, candidate_id)


_EXPORT_FIELDS: tuple[ExportField, ...] = get_args(ExportField)


def _export_value(c: CandidateRead, field: ExportField) -> str | int | float | None:
    match field:
        case "rank":
            return c.rank
        case "origin":
            return c.origin
        case "seller":
            return c.seller_org_name
        case "seller_attio_id":
            return c.seller_attio_id
        case "match_score":
            return c.match_score
        case "data_confidence":
            return c.data_confidence
        case "status":
            return c.status
        case "why_it_matches":
            return c.why_it_matches
        case "why_chosen_over_alternatives":
            return c.why_chosen_over_alternatives
        case "recommended_pitch":
            return c.recommended_pitch
        case "risks_and_gaps":
            return c.risks_and_gaps
        case "source_url":
            return c.source_url
        case "research_saved":
            saved = [f.name for f in c.research.fields if f.saved] if c.research else []
            return ", ".join(saved) or None


@router.get(
    "/match-runs/{run_id}/export.csv",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}}},
)
async def export_match_run(
    run_id: uuid.UUID,
    service: Service,
    fields: Annotated[list[ExportField] | None, Query()] = None,
) -> Response:
    """`fields` picks and orders the columns; omitted, every column is exported."""
    columns = list(dict.fromkeys(fields)) if fields else list(_EXPORT_FIELDS)
    detail = await _run_detail(service, run_id, await _load_run(service, run_id))
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(columns)
    for c in detail.candidates:
        writer.writerow([_csv_cell(_export_value(c, f)) for f in columns])
    filename = f"find-match-{run_id}.csv"
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _csv_cell(value: str | int | float | None) -> str:
    text = "" if value is None else str(value)
    # LLM-written text reaches Excel; a leading formula character must not execute.
    return f"'{text}" if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


async def _load_run(service: MatchingEngineService, run_id: uuid.UUID) -> MatchAnalysisData:
    analysis = await service.get_match_analysis(run_id)
    if analysis is None:
        raise api_error(status.HTTP_404_NOT_FOUND, _not_found("Run not found."))
    return analysis


def _require_candidate(analysis: MatchAnalysisData, candidate_id: uuid.UUID) -> MatchResultEntity:
    candidate = next((c for c in analysis.candidates if c.id == str(candidate_id)), None)
    if candidate is None:
        raise api_error(status.HTTP_404_NOT_FOUND, _not_found("Candidate not found in this run."))
    return candidate


async def _decided(
    service: MatchingEngineService, run_id: uuid.UUID, candidate_id: uuid.UUID
) -> DecisionResponse:
    detail = await _run_detail(service, run_id, await _load_run(service, run_id))
    candidate = next(c for c in detail.candidates if c.id == candidate_id)
    return DecisionResponse(candidate=candidate)


def _decision_error(exc: MatchNotFoundError | InvalidTransitionError) -> Exception:
    if isinstance(exc, MatchNotFoundError):
        return api_error(status.HTTP_404_NOT_FOUND, _not_found("Candidate not found."))
    return api_error(
        status.HTTP_409_CONFLICT,
        ApiError(code="already_reviewed", message="This candidate has already been reviewed."),
    )


async def _run_detail(
    service: MatchingEngineService, run_id: uuid.UUID, analysis: MatchAnalysisData
) -> RunDetailResponse:
    settings = get_settings()
    now = datetime.now(UTC)
    stale_after = timedelta(minutes=settings.match_run_stale_after_minutes)
    tracked = run_tracker.get(run_id)
    profiles = {
        p.seller_role_id: p
        for p in await service.get_seller_profiles(
            [c.seller_role_id for c in analysis.candidates if c.seller_role_id]
        )
    }
    run = analysis.run
    state = run_state(
        status=run.status,
        started_at=run.started_at,
        completed_at=run.completed_at,
        now=now,
        stale_after=stale_after,
    )
    if state == "stale" and tracked is not None and tracked.executing:
        state = "running"
    reasoning = {s.seller_attio_id: s.reasoning for s in analysis.scores}
    criteria = {
        s.seller_attio_id: [
            CriterionRead(
                criterion=c.criterion,
                criterion_type=c.criterion_type,
                result=c.result,
                data_backing=c.data_backing,
            )
            for c in s.dims.criteria
        ]
        for s in analysis.scores
    }
    candidates = [_candidate(c, reasoning, criteria, profiles) for c in analysis.candidates]
    crm_scores = [c.match_score or 0.0 for c in candidates if c.origin == "crm"]
    low_quality = state == "completed" and needs_web_fallback(
        crm_scores, settings.web_fallback_min_score
    )

    record = run.discovery
    if tracked is not None and tracked.discovery is not None:
        discovery = DiscoveryRead(
            status=tracked.discovery.status,
            message=tracked.discovery.message,
            notes=list(tracked.discovery.notes),
        )
    elif record is not None and record.outcome is not None:
        # Kept on the run row, so Slack's searches and pre-restart ones show too.
        discovery = DiscoveryRead(
            status=record.outcome, message=record.message, notes=list(record.notes)
        )
    elif record is not None and now - record.claimed_at <= stale_after:
        discovery = DiscoveryRead(status="running")
    elif any(c.origin == "discovery" for c in candidates):
        discovery = DiscoveryRead(status="done")
    elif low_quality:
        # The tracker lost this run (restart); the advisor can start the search by hand.
        discovery = DiscoveryRead(status="available")
    else:
        discovery = DiscoveryRead(status="not_needed")

    error = run.errors.get("message") if run.errors else None
    return RunDetailResponse(
        run_id=run_id,
        buyer_role_id=run.buyer_role_id,
        buyer_org_name=run.buyer_org_name or run.buyer_attio_id,
        state=state,
        started_at=run.started_at,
        completed_at=run.completed_at,
        error=error if isinstance(error, str) else None,
        candidates_considered=run.candidates_considered,
        candidates_filtered=run.candidates_filtered,
        low_match_quality=low_quality,
        discovery_threshold=settings.web_fallback_min_score,
        notes=list(tracked.notes) if tracked is not None else [],
        discovery=discovery,
        candidates=candidates,
        mandate=_mandate(run.requirement_profile) if run.requirement_profile else None,
    )


def _mandate(profile: RequirementProfile) -> MandateRead:
    return MandateRead(
        strategic_thesis=profile.strategic_thesis,
        ideal_target=profile.ideal_target_description,
        hard_requirements=[
            HardRequirementRead(
                criterion=r.criterion,
                value=r.value,
                source=r.source,
                human_confirmed=r.human_confirmed,
            )
            for r in profile.hard_requirements
        ],
    )


def _candidate(
    c: MatchResultEntity,
    reasoning: dict[str, str | None],
    criteria: dict[str, list[CriterionRead]],
    profiles: dict[str, SellerProfile],
) -> CandidateRead:
    profile = profiles.get(c.seller_role_id) if c.seller_role_id else None
    return CandidateRead(
        id=uuid.UUID(c.id),
        rank=c.rank or 0,
        origin=c.origin,
        seller_org_name=c.seller_org_name or c.seller_attio_id or "Unknown",
        seller_attio_id=c.seller_attio_id,
        source_url=c.source_url,
        match_score=c.match_score,
        data_confidence=c.data_confidence,
        why_it_matches=reasoning.get(c.seller_attio_id) if c.seller_attio_id else None,
        why_chosen_over_alternatives=c.why_chosen_over_alternatives,
        recommended_pitch=c.recommended_pitch,
        risks_and_gaps=c.risks_and_gaps,
        status=c.status,
        decision=c.decision,
        decided_at=c.decided_at,
        deal_attio_id=c.deal_attio_id,
        profile=_profile(profile) if profile else None,
        # Discovered sellers are unscored, so like Slack they show no breakdown.
        criteria=criteria.get(c.seller_attio_id, [])
        if c.seller_attio_id and c.match_score is not None
        else [],
        research=_research(c.research) if c.research else None,
    )


def _research(r: ResearchRecord) -> ResearchRead:
    stale_before = datetime.now(UTC) - research_stale_after()
    status_now = r.status(stale_before=stale_before)
    linkedin = r.linkedin
    return ResearchRead(
        status=status_now,
        started_at=r.claimed_at,
        error=r.error
        or ("Research stopped before it finished." if status_now == "failed" else None),
        fields=[
            ResearchFieldRead(
                name=f.name,
                target=f.target,
                display=f.display,
                confidence=f.confidence,
                source_url=f.source_url,
                rationale=f.rationale,
                saved=f.name in r.saved_fields,
            )
            for f in r.fields
        ],
        linkedin=ResearchLinkedInRead(
            outcome=linkedin.outcome,
            posts=[
                ResearchPostRead(
                    url=p.url, text=p.text, author_name=p.author_name, posted_at=p.posted_at
                )
                for p in linkedin.posts
            ],
            job_changes=[
                ResearchJobChangeRead(
                    name=j.name, title=j.title, company=j.company, source_url=j.source_url
                )
                for j in linkedin.job_changes
            ],
            contacts_without_linkedin=linkedin.contacts_without_linkedin,
        )
        if linkedin
        else None,
        reviewed=status_now == "done" and r.reviewed,
    )


def _profile(p: SellerProfile) -> SellerProfileRead:
    return SellerProfileRead(
        description=p.description,
        hq_country=p.hq_country,
        sector_focus=p.sector_focus,
        website=p.website,
        employee_range=p.employee_range,
        founded_year=p.founded_year,
        location_count=p.location_count,
        est_revenue=_money(p.est_revenue),
        est_ebitda=_money(p.est_ebitda),
    )


def _money(m: Money | None) -> MoneyRead | None:
    if m is None or m.amount is None:
        return None
    return MoneyRead(amount=m.amount, currency=m.currency or "USD")
