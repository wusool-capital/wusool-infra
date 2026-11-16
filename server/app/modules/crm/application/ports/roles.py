"""What the CRM service needs from storage and from the CRM write path."""

from typing import Literal, Protocol

from app.modules.crm.domain.roles import (
    BuyerChanges,
    BuyerFilters,
    BuyerRole,
    BuyersPage,
    Detail,
    FieldDef,
    NewBuyer,
    NewSeller,
    SellerChanges,
    SellerFilters,
    SellerRole,
    SellersPage,
    SignedInUser,
)


class RolesReaderPort(Protocol):
    async def buyers_page(
        self, filters: BuyerFilters, cursor: str | None, limit: int
    ) -> BuyersPage: ...

    async def sellers_page(
        self, filters: SellerFilters, cursor: str | None, limit: int
    ) -> SellersPage: ...

    async def buyer(self, role_id: str) -> BuyerRole | None: ...

    async def seller(self, role_id: str) -> SellerRole | None: ...

    async def member_by_email(self, email: str) -> SignedInUser | None: ...


class RoleWriterPort(Protocol):
    """Writes Attio first, then Postgres, and records the person who clicked."""

    async def add_buyer(
        self, buyer: NewBuyer, *, requested_by: str
    ) -> tuple[Literal["added", "existing"], str]:
        """Returns the outcome and the id of the role that was added or already existed."""
        ...

    def buyer_statuses(self) -> tuple[str, ...]:
        """The statuses Attio allows a buyer to have."""
        ...

    def buyer_regions(self) -> tuple[str, ...]:
        """The target regions Attio allows."""
        ...

    def buyer_countries(self) -> tuple[str, ...]:
        """The target countries Attio allows."""
        ...

    def hq_countries(self) -> tuple[str, ...]:
        """The HQ countries Attio allows a company to have."""
        ...

    def buyer_sectors(self) -> tuple[str, ...]:
        """The target verticals Attio allows a buyer role to have."""
        ...

    def appetite_signals(self) -> tuple[str, ...]:
        """The appetite signals Attio allows a seller role to have."""
        ...

    def seller_sectors(self) -> tuple[str, ...]:
        """The sectors Attio allows a company to focus on."""
        ...

    def buyer_fields(self) -> tuple[FieldDef, ...]:
        """The buyer and company fields Slack takes that the Engine has no fixed control for."""
        ...

    def seller_fields(self) -> tuple[FieldDef, ...]:
        """The same for sellers."""
        ...

    async def record_details(
        self, kind: Literal["buyer", "seller"], role_id: str
    ) -> tuple[Detail, ...]:
        """Current values of those fields for one role."""
        ...

    async def add_seller(
        self, seller: NewSeller, *, requested_by: str
    ) -> tuple[Literal["added", "existing"], str]: ...

    async def edit_buyer(
        self, role_id: str, changes: BuyerChanges, *, requested_by: str
    ) -> None: ...

    async def edit_seller(
        self, role_id: str, changes: SellerChanges, *, requested_by: str
    ) -> None: ...
