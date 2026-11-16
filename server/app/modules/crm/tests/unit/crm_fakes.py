from dataclasses import dataclass, field, replace
from typing import Literal

from app.modules.crm.domain.roles import (
    BuyerChanges,
    BuyerFilterOptions,
    BuyerFilters,
    BuyerRole,
    BuyersPage,
    Detail,
    FieldDef,
    NewBuyer,
    NewSeller,
    SellerChanges,
    SellerFilterOptions,
    SellerFilters,
    SellerRole,
    SellersPage,
    SignedInUser,
)

JULES = SignedInUser(id="attio-jules", name="Jules", email="jules@wusoolcapital.com")


def buyer(role_id: str = "b1", etag: str = "v1") -> BuyerRole:
    return BuyerRole(
        id=role_id,
        name="Acme Capital",
        hq="United Arab Emirates",
        website="acme.com",
        sectors=("Dental",),
        geographies=("GCC",),
        check_size_min_usd=1e6,
        check_size_max_usd=5e6,
        ebitda_floor_usd=None,
        owner_id="attio-jules",
        status="Active",
        contact_ids=(),
        notes=None,
        etag=etag,
    )


def seller(role_id: str = "s1", etag: str = "v1") -> SellerRole:
    return SellerRole(
        id=role_id,
        name="Smile Clinics",
        hq="Qatar",
        website="smile.example",
        sector="Dental",
        geography="GCC",
        est_revenue_usd=None,
        est_ebitda_usd=None,
        open_to_selling="Unknown",
        re_engage_date=None,
        owner_id=None,
        contact_ids=(),
        etag=etag,
    )


@dataclass
class FakeReader:
    buyers: dict[str, BuyerRole] = field(default_factory=lambda: {"b1": buyer()})
    sellers: dict[str, SellerRole] = field(default_factory=lambda: {"s1": seller()})
    members: dict[str, SignedInUser] = field(default_factory=lambda: {JULES.email: JULES})
    seen_filters: list[BuyerFilters | SellerFilters] = field(default_factory=list)
    seen_limits: list[int] = field(default_factory=list)

    async def buyers_page(
        self, filters: BuyerFilters, cursor: str | None, limit: int
    ) -> BuyersPage:
        self.seen_filters.append(filters)
        self.seen_limits.append(limit)
        rows = tuple(self.buyers.values())
        options = BuyerFilterOptions(("Dental",), ("GCC",), ("Active",))
        return BuyersPage(rows, (), (), len(rows), len(rows), None, options)

    async def sellers_page(
        self, filters: SellerFilters, cursor: str | None, limit: int
    ) -> SellersPage:
        self.seen_filters.append(filters)
        self.seen_limits.append(limit)
        rows = tuple(self.sellers.values())
        return SellersPage(
            rows, (), (), len(rows), len(rows), None, SellerFilterOptions(("Dental",), ("GCC",))
        )

    async def buyer(self, role_id: str) -> BuyerRole | None:
        return self.buyers.get(role_id)

    async def seller(self, role_id: str) -> SellerRole | None:
        return self.sellers.get(role_id)

    async def member_by_email(self, email: str) -> SignedInUser | None:
        return self.members.get(email)


@dataclass
class FakeWriter:
    reader: FakeReader
    add_outcome: Literal["added", "existing"] = "added"
    error: Exception | None = None
    edits: list[tuple[str, str]] = field(default_factory=list)
    changes: list[BuyerChanges] = field(default_factory=list)

    async def add_buyer(
        self, buyer_: NewBuyer, *, requested_by: str
    ) -> tuple[Literal["added", "existing"], str]:
        if self.error:
            raise self.error
        self.reader.buyers["b2"] = replace(buyer(), id="b2", name=buyer_.name)
        return self.add_outcome, "b2" if self.add_outcome == "added" else "b1"

    def buyer_statuses(self) -> tuple[str, ...]:
        return ("Active", "Dormant")

    def buyer_regions(self) -> tuple[str, ...]:
        return ("GCC", "Europe")

    def buyer_countries(self) -> tuple[str, ...]:
        return ("Qatar", "Oman")

    def hq_countries(self) -> tuple[str, ...]:
        return ("Qatar", "Oman", "Japan")

    def buyer_fields(self) -> tuple[FieldDef, ...]:
        return (
            FieldDef("model", "Model", "select", ("Model 1", "Model 2"), "role", True),
            FieldDef("investment_strategy", "Investment strategy", "multiline", (), "role", True),
            FieldDef(
                "client_type", "Client type", "multi_select", ("M&A", "Project"), "company", True
            ),
        )

    def seller_fields(self) -> tuple[FieldDef, ...]:
        return (
            FieldDef(
                "sell_timeline",
                "Sell timeline",
                "select",
                ("Immediate", "Not Selling"),
                "role",
                True,
            ),
            FieldDef(
                "sector_focus",
                "Sector focus",
                "multi_select",
                ("Dental", "Retail"),
                "company",
                False,
            ),
        )

    async def record_details(
        self, kind: Literal["buyer", "seller"], role_id: str
    ) -> tuple[Detail, ...]:
        return (Detail("model", "Model 1"), Detail("client_type", ("M&A",)))

    def seller_sectors(self) -> tuple[str, ...]:
        return ("Clinic", "Garage")

    def buyer_sectors(self) -> tuple[str, ...]:
        return ("Clinic", "Garage", "Legal Services")

    def appetite_signals(self) -> tuple[str, ...]:
        return ("No Signal", "Warm Introduction / Direct Outreach")

    async def add_seller(
        self, seller_: NewSeller, *, requested_by: str
    ) -> tuple[Literal["added", "existing"], str]:
        if self.error:
            raise self.error
        self.reader.sellers["s2"] = replace(seller(), id="s2", name=seller_.name)
        return self.add_outcome, "s2" if self.add_outcome == "added" else "s1"

    async def edit_buyer(self, role_id: str, changes: BuyerChanges, *, requested_by: str) -> None:
        if self.error:
            raise self.error
        self.edits.append((role_id, requested_by))
        self.changes.append(changes)
        self.reader.buyers[role_id] = replace(self.reader.buyers[role_id], etag="v2")

    async def edit_seller(self, role_id: str, changes: SellerChanges, *, requested_by: str) -> None:
        if self.error:
            raise self.error
        self.edits.append((role_id, requested_by))
        self.reader.sellers[role_id] = replace(self.reader.sellers[role_id], etag="v2")
