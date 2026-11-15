"""The `/benchmark` endpoint.

Follows the write contract: record the submission, respond to the visitor,
then do everything that can fail in the background. Nothing after the
response can lose the lead.
"""

from fastapi import APIRouter, BackgroundTasks, Depends

from app.modules.lead_magnets.api.analytics import track_lead
from app.modules.lead_magnets.api.dependencies import (
    SessionDep,
    rate_limit,
    require_allowed_origin,
)
from app.modules.lead_magnets.api.schemas import (
    BenchmarkRequest,
    BenchmarkResponse,
    FlagOut,
    ImpliedEvOut,
    MetricOut,
)
from app.modules.lead_magnets.application.shared.pipelines import score_benchmark
from app.modules.lead_magnets.bootstrap import build_submission_service, run_completion
from app.modules.lead_magnets.domain.benchmark.benchmark_submission import (
    BenchmarkResult,
)
from app.modules.lead_magnets.providers.benchmark_data.peer_dataset import load_peer_dataset

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
    run_id = await service.record(
        tool="benchmark",
        payload=request.model_dump(),
        email=request.email,
        domain=request.domain,
    )
    # Commit before anything that can fail, including the scoring below.
    # Two reasons, both load-bearing:
    #   1. The contract is that the lead is DURABLE before the visitor gets a
    #      response. Leaving it to dependency teardown means a crash in that
    #      window loses the lead — the exact failure this module prevents.
    #   2. The background task opens its own session, so an uncommitted row
    #      is invisible to it and the completion is skipped entirely.
    await session.commit()

    background.add_task(run_completion, run_id)
    track_lead(
        background,
        tool="benchmark",
        submission_id=request.submission_id,
        analytics=request.analytics,
        name=request.name,
        email=request.email,
        company=request.company,
    )

    # Scored after the row exists, so even an unexpected failure here leaves
    # the lead recorded rather than losing it to a 500. Scored once: the output
    # is stored on the run, so the Attio write and the emails use exactly the
    # figures the visitor sees, even if an advisor edits the dataset meanwhile.
    scored = score_benchmark(request.model_dump(), await load_peer_dataset())
    await service.store_ai(run_id, scored.output)
    await session.commit()
    result = scored.result
    return _benchmark_response(str(run_id), result)


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
