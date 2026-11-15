"""Thin routes: parse, authenticate, call the use case, return the view."""

from typing import Annotated

from fastapi import APIRouter, Header, Response

from app.modules.crm.api.dependencies import CurrentUser, Service
from app.modules.crm.api.problems import problem
from app.modules.crm.api.schemas import (
    BuyerCreate,
    BuyerFilterOptionsView,
    BuyerQuery,
    BuyerRolePage,
    BuyerRoleView,
    BuyerUpdate,
    MeView,
    ProblemDetail,
    SellerCreate,
    SellerFilterOptionsView,
    SellerQuery,
    SellerRolePage,
    SellerRoleView,
    SellerUpdate,
)

_PROBLEMS: dict[int | str, dict[str, type[ProblemDetail]]] = {
    status: {"model": ProblemDetail}
    for status in (400, 401, 403, 404, 409, 412, 422, 428, 502, 503)
}

router = APIRouter(prefix="/api/v1", tags=["crm"], responses=_PROBLEMS)

IfMatch = Annotated[str | None, Header()]


def _require_if_match(if_match: str | None) -> str:
    if not if_match:
        raise problem(
            428,
            "if_match_required",
            "Precondition required",
            "Reload the page and try again: this edit has no version to check against.",
        )
    return if_match


def _etag(response: Response, etag: str) -> None:
    response.headers["ETag"] = f'"{etag}"'


@router.get("/me", operation_id="getCurrentUser", response_model=MeView)
async def get_me(user: CurrentUser) -> MeView:
    return MeView(id=user.id, name=user.name, email=user.email)


@router.get("/buyer-roles", operation_id="listBuyerRoles", response_model=BuyerRolePage)
async def list_buyer_roles(
    _user: CurrentUser, service: Service, query: BuyerQuery
) -> BuyerRolePage:
    page = await service.buyers(query.to_domain(), query.cursor, query.limit)
    return BuyerRolePage(
        rows=[BuyerRoleView.model_validate(row) for row in page.rows],
        matched=page.matched,
        total=page.total,
        next_cursor=page.next_cursor,
        options=BuyerFilterOptionsView.model_validate(page.options),
    )


@router.post("/buyer-roles", operation_id="addBuyer", response_model=BuyerRoleView, status_code=201)
async def add_buyer(
    body: BuyerCreate, user: CurrentUser, service: Service, response: Response
) -> BuyerRoleView:
    role = await service.add_buyer(user, body.to_domain())
    response.headers["Location"] = f"/api/v1/buyer-roles/{role.id}"
    _etag(response, role.etag)
    return BuyerRoleView.model_validate(role)


@router.get("/buyer-roles/{role_id}", operation_id="getBuyerRole", response_model=BuyerRoleView)
async def get_buyer_role(
    role_id: str, _user: CurrentUser, service: Service, response: Response
) -> BuyerRoleView:
    role = await service.buyer(role_id)
    _etag(response, role.etag)
    return BuyerRoleView.model_validate(role)


@router.patch("/buyer-roles/{role_id}", operation_id="updateBuyer", response_model=BuyerRoleView)
async def update_buyer(
    role_id: str,
    body: BuyerUpdate,
    user: CurrentUser,
    service: Service,
    response: Response,
    if_match: IfMatch = None,
) -> BuyerRoleView:
    role = await service.edit_buyer(user, role_id, body.to_domain(), _require_if_match(if_match))
    _etag(response, role.etag)
    return BuyerRoleView.model_validate(role)


@router.get("/seller-roles", operation_id="listSellerRoles", response_model=SellerRolePage)
async def list_seller_roles(
    _user: CurrentUser, service: Service, query: SellerQuery
) -> SellerRolePage:
    page = await service.sellers(query.to_domain(), query.cursor, query.limit)
    return SellerRolePage(
        rows=[SellerRoleView.model_validate(row) for row in page.rows],
        matched=page.matched,
        total=page.total,
        next_cursor=page.next_cursor,
        options=SellerFilterOptionsView.model_validate(page.options),
    )


@router.post(
    "/seller-roles", operation_id="addSeller", response_model=SellerRoleView, status_code=201
)
async def add_seller(
    body: SellerCreate, user: CurrentUser, service: Service, response: Response
) -> SellerRoleView:
    role = await service.add_seller(user, body.to_domain())
    response.headers["Location"] = f"/api/v1/seller-roles/{role.id}"
    _etag(response, role.etag)
    return SellerRoleView.model_validate(role)


@router.get("/seller-roles/{role_id}", operation_id="getSellerRole", response_model=SellerRoleView)
async def get_seller_role(
    role_id: str, _user: CurrentUser, service: Service, response: Response
) -> SellerRoleView:
    role = await service.seller(role_id)
    _etag(response, role.etag)
    return SellerRoleView.model_validate(role)


@router.patch("/seller-roles/{role_id}", operation_id="updateSeller", response_model=SellerRoleView)
async def update_seller(
    role_id: str,
    body: SellerUpdate,
    user: CurrentUser,
    service: Service,
    response: Response,
    if_match: IfMatch = None,
) -> SellerRoleView:
    role = await service.edit_seller(user, role_id, body.to_domain(), _require_if_match(if_match))
    _etag(response, role.etag)
    return SellerRoleView.model_validate(role)
