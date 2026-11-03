"""Thin routes over the existing matching use cases, mirroring the Slack
`/find-match` flow step by step: search → preflight → run → review → export.
Every action re-validates against the database, as the Slack handlers do.
"""

import csv
import io
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, get_args

from fastapi import APIRouter, Depends, Query, Response, status

from app.modules.matching_engine.api.buyers import BuyerSummary
from app.modules.matching_engine.api.dependencies import (
    detached_matching_engine_service,
    find_buyer_discrepancies,
    resolve_buyer,
    resolve_buyer_by_id,
)
from app.modules.matching_engine.api.http.auth import WEB_ACTOR, api_error, require_web_api_key
from app.modules.matching_engine.api.http.run_tracker import run_tracker
from app.modules.matching_engine.api.http.schemas import (
    ApiError,
    ApiErrorResponse,
    ApproveRequest,
    CandidateRead,
    ContextReadingRead,
    DecisionResponse,
    DiscoveryRead,
    DiscrepancyRead,
    ExistingDealRead,
    ExportField,
    PreflightRequest,
    PreflightResponse,
    RunDetailResponse,
    StartRunRequest,
    StartRunResponse,
)
from app.modules.matching_engine.api.http.web_runs import discover_for_web_run, execute_web_run
from app.modules.matching_engine.application.approvals import (
    InvalidTransitionError,
    MatchNotFoundError,
)
from app.modules.matching_engine.application.errors import (
    ExistingDealsFoundError,
    PartialWriteError,
)
from app.modules.matching_engine.config import get_settings
from app.modules.matching_engine.domain.matching.entities import (
    MatchAnalysisData,
    MatchResultEntity,
)
from app.modules.matching_engine.domain.matching.run_state import run_state
from app.modules.matching_engine.domain.matching.scoring import needs_web_fallback
from app.modules.utilities import get_shared_task_runner

_task_runner = get_shared_task_runner()

_ERRORS: dict[int | str, dict[str, type[ApiErrorResponse]]] = {
    401: {"model": ApiErrorResponse},
    404: {"model": ApiErrorResponse},
    503: {"model": ApiErrorResponse},
}

router = APIRouter(
    prefix="/api",
    tags=["find-match"],
    dependencies=[Depends(require_web_api_key)],
    responses=_ERRORS,
    # Short operation ids become the generated client's function and hook names.
    generate_unique_id_function=lambda route: route.name,
)


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
async def start_match_run(body: StartRunRequest) -> StartRunResponse:
    buyer = await resolve_buyer_by_id(str(body.buyer_role_id))
    if buyer is None:
        raise api_error(status.HTTP_404_NOT_FOUND, _not_found("Buyer not found."))
    service = await detached_matching_engine_service()
    started = await service.start_run(buyer, None)
    _task_runner.run(
        lambda: execute_web_run(started, buyer, advisor_context=body.advisor_context),
        name=f"web-find-match:{started.run_id}",
    )
    return StartRunResponse(run_id=started.run_id)


@router.get("/match-runs/{run_id}", response_model=RunDetailResponse)
async def get_match_run(run_id: uuid.UUID) -> RunDetailResponse:
    return _run_detail(run_id, await _load_run(run_id))


@router.post(
    "/match-runs/{run_id}/discovery",
    response_model=RunDetailResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_discovery(run_id: uuid.UUID) -> RunDetailResponse:
    """The web's "Find more sellers": a repeat call is a no-op, as in Slack."""
    analysis = await _load_run(run_id)
    if analysis.run.completed_at is None or analysis.run.status == "FAILED":
        raise api_error(
            status.HTTP_409_CONFLICT,
            ApiError(code="run_not_ready", message="The run hasn't completed successfully."),
        )
    _task_runner.run(lambda: discover_for_web_run(run_id), name=f"web-discover:{run_id}")
    return _run_detail(run_id, analysis)


@router.post(
    "/match-runs/{run_id}/candidates/{candidate_id}/approve",
    response_model=DecisionResponse,
    responses={409: {"model": ApiErrorResponse}, 502: {"model": ApiErrorResponse}},
)
async def approve_candidate(
    run_id: uuid.UUID, candidate_id: uuid.UUID, body: ApproveRequest
) -> DecisionResponse:
    await _require_candidate(run_id, candidate_id)
    service = await detached_matching_engine_service()
    try:
        await service.approve_match(
            candidate_id,
            WEB_ACTOR,
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
        message = (
            "Couldn't write the deal to Attio. Nothing was saved."
            if not exc.landed
            else "Approval failed partway through. Already saved: "
            f"{'; '.join(exc.landed)}. Check the match's status before retrying."
        )
        raise api_error(
            status.HTTP_502_BAD_GATEWAY, ApiError(code="partial_write", message=message)
        ) from exc
    except (MatchNotFoundError, InvalidTransitionError) as exc:
        raise _decision_error(exc) from exc
    return await _decided(run_id, candidate_id)


@router.post(
    "/match-runs/{run_id}/candidates/{candidate_id}/reject",
    response_model=DecisionResponse,
    responses={409: {"model": ApiErrorResponse}},
)
async def reject_candidate(run_id: uuid.UUID, candidate_id: uuid.UUID) -> DecisionResponse:
    await _require_candidate(run_id, candidate_id)
    service = await detached_matching_engine_service()
    try:
        await service.reject_match(candidate_id, WEB_ACTOR)
    except (MatchNotFoundError, InvalidTransitionError) as exc:
        raise _decision_error(exc) from exc
    return await _decided(run_id, candidate_id)


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


@router.get(
    "/match-runs/{run_id}/export.csv",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}}},
)
async def export_match_run(
    run_id: uuid.UUID,
    fields: Annotated[list[ExportField] | None, Query()] = None,
) -> Response:
    """`fields` picks and orders the columns; omitted, every column is exported."""
    columns = list(dict.fromkeys(fields)) if fields else list(_EXPORT_FIELDS)
    detail = _run_detail(run_id, await _load_run(run_id))
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
    return f"'{text}" if text[:1] in ("=", "+", "-", "@") else text


async def _load_run(run_id: uuid.UUID) -> MatchAnalysisData:
    service = await detached_matching_engine_service()
    analysis = await service.get_match_analysis(run_id)
    if analysis is None:
        raise api_error(status.HTTP_404_NOT_FOUND, _not_found("Run not found."))
    return analysis


async def _require_candidate(run_id: uuid.UUID, candidate_id: uuid.UUID) -> None:
    analysis = await _load_run(run_id)
    if not any(c.id == str(candidate_id) for c in analysis.candidates):
        raise api_error(status.HTTP_404_NOT_FOUND, _not_found("Candidate not found in this run."))


async def _decided(run_id: uuid.UUID, candidate_id: uuid.UUID) -> DecisionResponse:
    detail = _run_detail(run_id, await _load_run(run_id))
    candidate = next(c for c in detail.candidates if c.id == candidate_id)
    return DecisionResponse(candidate=candidate)


def _decision_error(exc: MatchNotFoundError | InvalidTransitionError) -> Exception:
    if isinstance(exc, MatchNotFoundError):
        return api_error(status.HTTP_404_NOT_FOUND, _not_found("Candidate not found."))
    return api_error(
        status.HTTP_409_CONFLICT,
        ApiError(code="already_reviewed", message="This candidate has already been reviewed."),
    )


def _run_detail(run_id: uuid.UUID, analysis: MatchAnalysisData) -> RunDetailResponse:
    settings = get_settings()
    run = analysis.run
    state = run_state(
        status=run.status,
        started_at=run.started_at,
        completed_at=run.completed_at,
        now=datetime.now(UTC),
        stale_after=timedelta(minutes=settings.match_run_stale_after_minutes),
    )
    reasoning = {s.seller_attio_id: s.reasoning for s in analysis.scores}
    candidates = [_candidate(c, reasoning) for c in analysis.candidates]
    crm_scores = [c.match_score or 0.0 for c in candidates if c.origin == "crm"]
    low_quality = state == "completed" and needs_web_fallback(
        crm_scores, settings.web_fallback_min_score
    )

    tracked = run_tracker.get(run_id)
    if tracked is not None and tracked.discovery is not None:
        discovery = DiscoveryRead(
            status=tracked.discovery.status,
            message=tracked.discovery.message,
            notes=list(tracked.discovery.notes),
        )
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
    )


def _candidate(c: MatchResultEntity, reasoning: dict[str, str | None]) -> CandidateRead:
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
    )
