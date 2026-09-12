"""The `/readiness/score` endpoint.

Follows the write contract, with one deliberate exception: the model call
sits on the response path (see `readiness_score`'s docstring), since the
visitor's whole report is that call's output.
"""

from dataclasses import asdict
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.lead_magnets.api.dependencies import (
    SessionDep,
    rate_limit,
    require_allowed_origin,
)
from app.modules.lead_magnets.api.schemas import (
    DimensionOut,
    ReadinessRequest,
    ReadinessResponse,
    RecommendationOut,
)
from app.modules.lead_magnets.bootstrap import (
    build_llm,
    build_submission_service,
    build_tool_runs,
    run_completion,
)
from app.modules.lead_magnets.domain.readiness.readiness import (
    ReadinessAnswers,
    build_advisory_content,
)
from app.modules.lead_magnets.domain.shared.prompts import readiness_score_prompt
from app.modules.lead_magnets.domain.shared.schemas import ReadinessResult
from app.modules.utilities.domain.provider_errors import BedrockInvocationError

router = APIRouter(
    tags=["lead-magnets"],
    dependencies=[Depends(require_allowed_origin), Depends(rate_limit)],
)


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
    run_id, outcome = await service.record(
        tool="readiness",
        payload={**request.model_dump(), "advisory_rules": asdict(build_advisory_content(answers))},
        email=request.email,
        domain=request.domain,
    )
    await session.commit()

    # Checked before the model call, not just before the background task —
    # this is the one tool where skipping a duplicate also saves a paid
    # Bedrock call, not just a redundant Attio write.
    if outcome == "duplicate":
        raise HTTPException(status.HTTP_409_CONFLICT, "you have already completed this")

    if outcome == "replay":
        # The exact same request as before, not a new person — must not
        # pay for a second Bedrock call. The original attempt's score is
        # already stored (`_store_score` below), unless it died before
        # reaching that point, in which case there is nothing to replay
        # and this falls through to the model call like "new" would.
        existing = await build_tool_runs(session).get(run_id)
        stored_score = existing.payload.get("score") if existing else None
        if stored_score is not None:
            background.add_task(run_completion, run_id)
            replayed = ReadinessResult.model_validate(stored_score)
            return ReadinessResponse(
                run_id=str(run_id),
                overallScore=replayed.overallScore,
                scoreBand=replayed.scoreBand,
                summaryParagraph=replayed.summaryParagraph,
                dimensions=[DimensionOut(**d.model_dump()) for d in replayed.dimensions],
                recommendations=[
                    RecommendationOut(**r.model_dump()) for r in replayed.recommendations
                ],
            )

    # The model call is on the response path here, unlike every other tool:
    # the visitor's whole report is its output, so there is nothing to show
    # without it. The lead is already safe either way.
    try:
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
    except BedrockInvocationError as exc:
        await build_tool_runs(session).finish(run_id, "failed", error=str(exc))
        await session.commit()
        raise
    # Handed to the background half so the advisory note does not pay for a
    # second scoring call: `Pipelines._readiness` reuses `payload.score`.
    await _store_score(session, run_id, scored)
    await session.commit()

    background.add_task(run_completion, run_id)

    return ReadinessResponse(
        run_id=str(run_id),
        overallScore=scored.overallScore,
        scoreBand=scored.scoreBand,
        summaryParagraph=scored.summaryParagraph,
        dimensions=[DimensionOut(**d.model_dump()) for d in scored.dimensions],
        recommendations=[RecommendationOut(**r.model_dump()) for r in scored.recommendations],
    )


async def _store_score(session: AsyncSession, run_id: UUID, scored: ReadinessResult) -> None:
    """Stores the scoring result so the background advisory reuses it rather
    than calling the model a second time for the same report."""
    from sqlalchemy import literal, update
    from sqlalchemy.dialects.postgresql import JSONB

    from app.models.tool_run import ToolRun

    await session.execute(
        update(ToolRun)
        .where(ToolRun.id == run_id)
        .values(payload=ToolRun.payload.op("||")(literal({"score": scored.model_dump()}, JSONB)))
    )
