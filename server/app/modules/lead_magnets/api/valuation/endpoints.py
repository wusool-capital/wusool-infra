"""`/enrich`, `/analyze` and `/compare` — the valuation tool's AI endpoints.

All three are stateless: they build the report the visitor reads while
still in the tool, long before there is a submission to record. The
valuation submission itself is not implemented yet (see the module README's
"Not built yet").
"""

from fastapi import APIRouter, Depends

from app.modules.lead_magnets.api.dependencies import rate_limit, require_allowed_origin
from app.modules.lead_magnets.api.schemas import (
    AnalyzeRequest,
    ComparableOut,
    CompareRequest,
    CompareResponse,
    EnrichRequest,
    EnrichResponse,
)
from app.modules.lead_magnets.bootstrap import build_valuation_ai
from app.modules.utilities.domain.json_types import JsonObject

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
    return EnrichResponse(
        description=result.get("description", ""), sector=result.get("sector", "")
    )


@router.post("/analyze")
async def analyze(request: AnalyzeRequest) -> JsonObject:
    """Sector judgement, discounts, DCF overrides, the strategic read and the
    readiness scorecard — the merge of what were separate calls.

    Runs in parallel with `/compare`; the two were split so the preview is
    ready when the loading screen ends.
    """
    return await build_valuation_ai().analyze(
        company=request.company,
        domain=request.domain,
        sector=request.sector,
        description=request.description,
        geography=request.geography,
        revenue=request.revenue,
        ebitda=request.ebitda,
        website_text=request.website_text,
    )


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
        comps=[ComparableOut(**c) for c in result["comps"]],
        sourced=result["sourced"],
        filled_from_static=result["filled_from_static"],
    )
