"""The lead-magnet endpoints.

Both follow the write contract: record the submission, respond to the
visitor, then do everything that can fail in the background. Nothing after
the response can lose the lead.

`/enrich`, `/analyze`, `/compare` and `/buyer/apply` are specified but not
implemented yet — they need the valuation prompts and the Buyer Network
form, which are still to port. They are deliberately absent rather than
stubbed: a 404 is honest, a stub that returns empty data is not.
"""

import logging
from dataclasses import asdict
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.lead_magnets.api.dependencies import (
    SessionDep,
    rate_limit,
    require_allowed_origin,
)
from app.modules.lead_magnets.api.schemas import (
    BenchmarkRequest,
    BenchmarkResponse,
    DimensionOut,
    FlagOut,
    ImpliedEvOut,
    MetricOut,
    ReadinessRequest,
    ReadinessResponse,
    RecommendationOut,
)
from app.modules.lead_magnets.bootstrap import (
    build_llm,
    build_submission_service,
    run_completion,
)
from app.modules.lead_magnets.domain.benchmark_submission import (
    BenchmarkInputs,
    BenchmarkResult,
    evaluate,
)
from app.modules.lead_magnets.domain.prompts import (
    readiness_score_prompt,
)
from app.modules.lead_magnets.domain.readiness import (
    ReadinessAnswers,
    build_advisory_content,
)
from app.modules.utilities.domain.json_types import JsonObject

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["lead-magnets"],
    dependencies=[Depends(require_allowed_origin), Depends(rate_limit)],
)


@router.post("/benchmark", response_model=BenchmarkResponse)
async def benchmark(
    request: BenchmarkRequest, session: SessionDep, background: BackgroundTasks
) -> BenchmarkResponse:
    """The GCC SME Benchmark. No model is involved in the visitor's result —
    it is scored entirely against the peer dataset, which is why this tool
    can never show an error for an AI failure and is the safest to cut over
    first.

    Keeps the path the live page already posts to.
    """
    service = build_submission_service(session)
    run_id, is_new = await service.record(
        tool="benchmark",
        payload=request.model_dump(),
        email=request.email,
        domain=request.domain,
        submission_id=request.submission_id,
    )
    # Commit before anything that can fail, including the scoring below.
    # Two reasons, both load-bearing:
    #   1. The contract is that the lead is DURABLE before the visitor gets a
    #      response. Leaving it to dependency teardown means a crash in that
    #      window loses the lead — the exact failure this module prevents.
    #   2. The background task opens its own session, so an uncommitted row
    #      is invisible to it and the completion is skipped entirely.
    await session.commit()

    if is_new:
        background.add_task(run_completion, run_id)

    # Scored after the row exists, so even an unexpected failure here leaves
    # the lead recorded rather than losing it to a 500.
    result = evaluate(
        BenchmarkInputs(
            mode=request.mode,
            peer_key=request.peer_key,
            revenue=request.revenue,
            prev_revenue=request.prev_revenue,
            ebitda_reported=request.ebitda_reported,
            owner_salary=request.owner_salary,
            salary_deducted=request.salary_deducted,
            gross_margin_pct=request.gross_margin_pct,
            headcount=request.headcount,
            rent_cost=request.rent_cost,
            capital_raised=request.capital_raised,
            top_customer_pct=request.top_customer_pct,
            recurring_pct=request.recurring_pct,
            years_active=request.years_active,
            outlets=request.outlets,
            days_to_get_paid=request.days_to_get_paid,
            email=request.email,
            geography=request.geography,
        )
    )
    return _benchmark_response(str(run_id), result)


@router.post("/readiness/score", response_model=ReadinessResponse)
async def readiness_score(
    request: ReadinessRequest, session: SessionDep, background: BackgroundTasks
) -> ReadinessResponse:
    """The M&A Readiness score.

    The one tool with no deterministic fallback: its score, band and
    recommendations come only from the model. A failed call means the
    visitor sees an error — the write-ahead row is what keeps the lead, and
    is why the submission is recorded before this call rather than after it,
    as the live tool does.
    """
    answers = ReadinessAnswers(**request.answers.model_dump())
    service = build_submission_service(session)
    run_id, is_new = await service.record(
        tool="readiness",
        payload={**request.model_dump(), "advisory_rules": asdict(build_advisory_content(answers))},
        email=request.email,
        domain=request.domain,
        submission_id=request.submission_id,
    )
    await session.commit()

    # The model call is on the response path here, unlike every other tool:
    # the visitor's whole report is its output, so there is nothing to show
    # without it. The lead is already safe either way.
    scored = await build_llm().score_readiness(
        prompt=readiness_score_prompt(
            founder=request.name,
            business=request.company,
            sector=request.sector,
            revenue_range=request.revenue or "Not specified",
            country=request.country or "Not specified",
            answers=answers,
        )
    )
    # Handed to the background half so the advisory note does not pay for a
    # second scoring call: `Pipelines._readiness` reuses `payload.score`.
    await _store_score(session, run_id, scored)
    await session.commit()

    if is_new:
        background.add_task(run_completion, run_id)

    return ReadinessResponse(
        run_id=str(run_id),
        overallScore=scored["overallScore"],
        scoreBand=scored["scoreBand"],
        summaryParagraph=scored["summaryParagraph"],
        dimensions=[DimensionOut(**d) for d in scored["dimensions"]],
        recommendations=[RecommendationOut(**r) for r in scored["recommendations"]],
    )


async def _store_score(session: AsyncSession, run_id: UUID, scored: JsonObject) -> None:
    """Stores the scoring result so the background advisory reuses it rather
    than calling the model a second time for the same report."""
    from sqlalchemy import literal, update
    from sqlalchemy.dialects.postgresql import JSONB

    from app.models.tool_run import ToolRun

    await session.execute(
        update(ToolRun)
        .where(ToolRun.id == run_id)
        .values(payload=ToolRun.payload.op("||")(literal({"score": scored}, JSONB)))
    )


def _benchmark_response(run_id: str, result: BenchmarkResult) -> BenchmarkResponse:
    return BenchmarkResponse(
        run_id=run_id,
        score=result.score,
        band=result.band,
        quartile=result.quartile,
        peer_label=result.peer_label,
        revenue_band=result.revenue_band.label,
        sample_size=result.sample_size,
        metrics={
            key: MetricOut(
                label=m.spec.label,
                value=m.value,
                percentile=m.percentile,
                quartile=m.quartile,
                peer_median=m.anchors[2] if m.anchors else None,
            )
            for key, m in result.metrics.items()
        },
        flags=[FlagOut(tone=f.tone, title=f.title, body=f.body) for f in result.flags],
        data_completeness=result.data_completeness,
        metrics_covered=result.metrics_covered,
        metrics_total=result.metrics_total,
        implied_ev=(
            ImpliedEvOut(
                low=result.implied_ev.low,
                mid=result.implied_ev.mid,
                high=result.implied_ev.high,
                forward_revenue=result.implied_ev.forward_revenue,
            )
            if result.implied_ev
            else None
        ),
    )
