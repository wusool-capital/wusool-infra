"""Page reads: one endpoint per Engine page, composed from `crm` and nothing else.

A block whose source is not live yet comes back empty and named in `unavailable`,
so the page loads with that block blank.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from app.modules.crm import (
    BuyerFilterOptionsView,
    BuyerQuery,
    BuyerRoleView,
    CrmService,
    CurrentUser,
    PersonView,
    ProblemDetail,
    SellerFilterOptionsView,
    SellerQuery,
    SellerRoleView,
    TeamMemberView,
    crm_service,
)
from app.modules.engine.api.schemas import BuyersUniverseView, Reserved, SellersUniverseView

_PROBLEMS: dict[int | str, dict[str, type[ProblemDetail]]] = {
    status: {"model": ProblemDetail} for status in (400, 401, 403, 422, 503)
}

_UNAVAILABLE: list[Reserved] = ["mandates", "outreach"]

router = APIRouter(prefix="/api/v1/views", tags=["engine"], responses=_PROBLEMS)

Service = Annotated[CrmService, Depends(crm_service)]


@router.get("/buyers", operation_id="getBuyersUniverse", response_model=BuyersUniverseView)
async def get_buyers_universe(
    _user: CurrentUser, service: Service, query: BuyerQuery
) -> BuyersUniverseView:
    page = await service.buyers(query.to_domain(), query.cursor, query.limit)
    return BuyersUniverseView(
        now=datetime.now(UTC),
        users=[TeamMemberView.model_validate(u) for u in page.users],
        people=[PersonView.model_validate(p) for p in page.people],
        unavailable=_UNAVAILABLE,
        matched=page.matched,
        total=page.total,
        next_cursor=page.next_cursor,
        buyers=[BuyerRoleView.model_validate(r) for r in page.rows],
        options=BuyerFilterOptionsView.model_validate(page.options),
    )


@router.get("/sellers", operation_id="getSellersUniverse", response_model=SellersUniverseView)
async def get_sellers_universe(
    _user: CurrentUser, service: Service, query: SellerQuery
) -> SellersUniverseView:
    page = await service.sellers(query.to_domain(), query.cursor, query.limit)
    return SellersUniverseView(
        now=datetime.now(UTC),
        users=[TeamMemberView.model_validate(u) for u in page.users],
        people=[PersonView.model_validate(p) for p in page.people],
        unavailable=_UNAVAILABLE,
        matched=page.matched,
        total=page.total,
        next_cursor=page.next_cursor,
        sellers=[SellerRoleView.model_validate(r) for r in page.rows],
        options=SellerFilterOptionsView.model_validate(page.options),
    )
