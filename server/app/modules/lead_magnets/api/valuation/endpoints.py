"""`/enrich`, `/analyze`, `/compare` and `/submit-lead` — the valuation
tool's endpoints.

`/enrich`, `/analyze` and `/compare` are stateless: they build the report
the visitor reads while still in the tool, long before there is a
submission to record. `/submit-lead` is the write-contract endpoint — the
one that actually records the lead.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.modules.lead_magnets.api.dependencies import (
    SessionDep,
    rate_limit,
    require_allowed_origin,
)
from app.modules.lead_magnets.api.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    ComparableOut,
    CompareRequest,
    CompareResponse,
    EnrichRequest,
    EnrichResponse,
    MethodRowOut,
    ValuationRequest,
    ValuationResponse,
)
from app.modules.lead_magnets.bootstrap import (
    build_submission_service,
    build_valuation_ai,
    run_completion,
)
from app.modules.lead_magnets.domain.valuation.valuation_data import ListedComp
from app.modules.lead_magnets.domain.valuation.valuation_methods import (
    ValuationInputs,
    value_company,
)

router = APIRouter(
    tags=["lead-magnets"],
    dependencies=[Depends(require_allowed_origin), Depends(rate_limit)],
)


@router.post("/enrich", response_model=EnrichResponse)
async def enrich(request: EnrichRequest) -> EnrichResponse:
    """Description and sector from the company's own page.

    Stateless: this runs as the visitor types their website address, long
    before there is a submission to record.
    """
    result = await build_valuation_ai().enrich(domain=request.domain, company=request.company)
    return EnrichResponse(description=result.description, sector=result.sector)


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    """Sector judgement, discounts, DCF overrides, the strategic read and the
    readiness scorecard — the merge of what were separate calls.

    Runs in parallel with `/compare`; the two were split so the preview is
    ready when the loading screen ends.

    A Bedrock failure no longer surfaces as a bare error: `ValuationAi`
    falls back to the deterministic pros/cons/insights, so the response is
    partial rather than absent.
    """
    result = await build_valuation_ai().analyze(
        company=request.company,
        domain=request.domain,
        sector=request.sector,
        description=request.description,
        geography=request.geography,
        revenue=request.revenue,
        ebitda=request.ebitda,
        website_text=request.website_text,
        raised=request.raised,
        stage=request.stage,
    )
    return AnalyzeResponse(**result)


@router.post("/compare", response_model=CompareResponse)
async def compare(request: CompareRequest) -> CompareResponse:
    """Comparable listed companies, grounded in search results.

    Bedrock cannot search for Claude, so this is the replacement pipeline: a
    cheap model plans the queries, Firecrawl runs them, the main model
    selects from the results, and any shortfall is filled from the static
    sector set rather than by inventing figures.
    """
    result = await build_valuation_ai().compare(
        company=request.company,
        sector=request.sector,
        description=request.description,
        revenue=request.revenue,
        geography=request.geography,
    )
    return CompareResponse(
        comps=[ComparableOut(**c.model_dump()) for c in result.comps],
        sourced=result.sourced,
        filled_from_static=result.filled_from_static,
    )


@router.post("/submit-lead", response_model=ValuationResponse)
async def submit_lead(
    request: ValuationRequest, session: SessionDep, background: BackgroundTasks
) -> ValuationResponse:
    """The blended valuation — DCF, trading comps, transaction comps.

    No model call here or in the background: the blend is entirely
    deterministic once `/compare`'s comparables and `/analyze`'s discount
    overrides are in hand (or absent, in which case `ValuationInputs`' own
    per-method defaults apply), so the response is computed inline rather
    than deferred. The background task still exists — it writes the ledger
    row to Attio, exactly like every other tool.
    """
    service = build_submission_service(session)
    run_id, is_new = await service.record(
        tool="valuation",
        payload=request.model_dump(),
        email=request.email,
        domain=request.domain,
    )
    await session.commit()

    if not is_new:
        raise HTTPException(status.HTTP_409_CONFLICT, "you have already completed this")

    background.add_task(run_completion, run_id)

    # Omitted rather than passed as `None` when absent: `ValuationInputs`'
    # own per-method defaults already apply, and staying in sync with those
    # defaults is free this way rather than duplicating the numbers here.
    # One AI-judged discount pair, when present, applies to both trading
    # and transaction comps alike (the model gives one opinion, not four).
    haircuts: dict[str, float] = {}
    if request.discounts:
        if request.discounts.revenue_discount_pct is not None:
            haircuts["trading_haircut_revenue_pct"] = request.discounts.revenue_discount_pct
            haircuts["transaction_haircut_revenue_pct"] = request.discounts.revenue_discount_pct
        if request.discounts.ebitda_discount_pct is not None:
            haircuts["trading_haircut_ebitda_pct"] = request.discounts.ebitda_discount_pct
            haircuts["transaction_haircut_ebitda_pct"] = request.discounts.ebitda_discount_pct

    result = value_company(
        ValuationInputs(
            revenue=request.revenue,
            profit_before_tax=request.profit_before_tax,
            owner_salary=request.owner_salary,
            sector=request.sector,
            geography=request.geography,
            stage=request.stage,
            cash=request.cash,
            debt=request.debt,
            ai_comps=tuple(
                ListedComp(co=c.co, tk=c.tk, ev=c.ev, rev=c.rev, ebitda=c.ebitda)
                for c in request.comps
            ),
            **haircuts,
        )
    )
    return ValuationResponse(
        run_id=str(run_id),
        low=result.low,
        mid=result.mid,
        high=result.high,
        methods=[
            MethodRowOut(name=m.name, low=m.low, mid=m.mid, high=m.high) for m in result.methods
        ],
    )
