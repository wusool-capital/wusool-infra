import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.auth import AccessClaims
from app.modules.crm import crm_service, install_problem_handlers
from app.modules.crm.api import dependencies
from app.modules.crm.domain.roles import (
    BuyerFilterOptions,
    BuyerFilters,
    BuyerRole,
    BuyersPage,
    Person,
    SellerFilterOptions,
    SellerFilters,
    SellerRole,
    SellersPage,
    SignedInUser,
    TeamMember,
)
from app.modules.engine import router

_JULES = SignedInUser(id="u1", name="Jules", email="jules@wusoolcapital.com")
_HEADERS = {"Cf-Access-Jwt-Assertion": "token"}


class _FakeService:
    def __init__(self) -> None:
        self.filters: list[BuyerFilters | SellerFilters] = []

    async def sign_in(self, email: str) -> SignedInUser | None:
        return _JULES if email == _JULES.email else None

    async def buyers(self, filters: BuyerFilters, cursor: str | None, limit: int) -> BuyersPage:
        self.filters.append(filters)
        buyer = BuyerRole(
            "b1", "Acme", "UAE", "acme.com", ("Dental",), ("GCC",), 1e6, 5e6, None, "u1",
            "Active", ("p1",), None, "v1",
        )  # fmt: skip
        return BuyersPage(
            (buyer,),
            (Person("p1", "Rania", "Acme", "buyer"),),
            (TeamMember("u1", "Jules"),),
            1,
            9,
            "next",
            BuyerFilterOptions(("Dental",), ("GCC",), ("Active",)),
        )

    async def sellers(self, filters: SellerFilters, cursor: str | None, limit: int) -> SellersPage:
        self.filters.append(filters)
        seller = SellerRole(
            id="s1", name="Smile", hq="Qatar", website=None, sector="Dental", geography="GCC",
            est_revenue_usd=None, est_ebitda_usd=None, open_to_selling="Interested",
            re_engage_date=None, owner_id=None, contact_ids=(), etag="v1",
        )  # fmt: skip
        return SellersPage(
            (seller,), (), (), 1, 4, None, SellerFilterOptions(("Dental",), ("GCC",))
        )


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, _FakeService]:
    service = _FakeService()
    app = FastAPI()
    app.include_router(router)
    install_problem_handlers(app)
    app.dependency_overrides[crm_service] = lambda: service

    async def verify(_token: str) -> AccessClaims:
        return AccessClaims(email=_JULES.email, sub="s")

    monkeypatch.setattr(dependencies, "access_configured", lambda: True)
    monkeypatch.setattr(dependencies, "verify_access_jwt", verify)
    return TestClient(app), service


def test_the_buyers_universe_has_the_engine_shape_and_blank_later_blocks(client) -> None:
    http, service = client

    response = http.get("/api/v1/views/buyers?sector=Dental&q=acme", headers=_HEADERS)

    body = response.json()
    assert response.status_code == 200
    assert body["buyers"][0]["checkSizeMinUsd"] == 1e6
    assert body["people"][0]["name"] == "Rania"
    assert (body["matched"], body["total"], body["nextCursor"]) == (1, 9, "next")
    assert (body["deals"], body["counterparties"], body["emails"]) == ([], [], [])
    assert body["unavailable"] == ["mandates", "outreach"]
    assert body["options"]["geographies"] == ["GCC"]
    assert service.filters[0].sectors == ("Dental",)


def test_the_sellers_universe_has_the_engine_shape(client) -> None:
    http, _ = client

    body = http.get("/api/v1/views/sellers?openToSelling=Interested", headers=_HEADERS).json()

    assert body["sellers"][0]["openToSelling"] == "Interested"
    assert (body["matched"], body["total"]) == (1, 4)
    assert body["unavailable"] == ["mandates", "outreach"]


def test_a_universe_needs_a_token(client) -> None:
    http, _ = client

    assert http.get("/api/v1/views/buyers").status_code == 401
