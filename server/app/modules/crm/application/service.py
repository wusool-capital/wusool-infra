"""The use cases behind the Engine's buyer and seller pages."""

from app.modules.crm.application.ports.roles import RolesReaderPort, RoleWriterPort
from app.modules.crm.domain.roles import (
    BuyerChanges,
    BuyerFilters,
    BuyerRole,
    BuyersPage,
    NewBuyer,
    RoleAlreadyExistsError,
    RoleNotFoundError,
    SellerChanges,
    SellerFilters,
    SellerRole,
    SellersPage,
    SignedInUser,
    StaleRoleError,
)

MAX_PAGE_SIZE = 100


def _same_version(etag: str, if_match: str) -> bool:
    # Entity tags travel quoted, and a proxy may mark them weak.
    return etag == if_match.removeprefix("W/").strip('"')


class CrmService:
    def __init__(self, reader: RolesReaderPort, writer: RoleWriterPort) -> None:
        self._reader = reader
        self._writer = writer

    async def sign_in(self, email: str) -> SignedInUser | None:
        return await self._reader.member_by_email(email)

    async def buyers(self, filters: BuyerFilters, cursor: str | None, limit: int) -> BuyersPage:
        return await self._reader.buyers_page(filters, cursor, min(limit, MAX_PAGE_SIZE))

    async def sellers(self, filters: SellerFilters, cursor: str | None, limit: int) -> SellersPage:
        return await self._reader.sellers_page(filters, cursor, min(limit, MAX_PAGE_SIZE))

    async def add_buyer(self, user: SignedInUser, buyer: NewBuyer) -> BuyerRole:
        outcome, role_id = await self._writer.add_buyer(buyer, requested_by=user.id)
        if outcome == "existing":
            raise RoleAlreadyExistsError(role_id)
        return await self._buyer(role_id)

    async def edit_buyer(
        self, user: SignedInUser, role_id: str, changes: BuyerChanges, if_match: str
    ) -> BuyerRole:
        current = await self._buyer(role_id)
        if not _same_version(current.etag, if_match):
            raise StaleRoleError(role_id)
        await self._writer.edit_buyer(role_id, changes, requested_by=user.id)
        return await self._buyer(role_id)

    async def edit_seller(
        self, user: SignedInUser, role_id: str, changes: SellerChanges, if_match: str
    ) -> SellerRole:
        current = await self._seller(role_id)
        if not _same_version(current.etag, if_match):
            raise StaleRoleError(role_id)
        await self._writer.edit_seller(role_id, changes, requested_by=user.id)
        return await self._seller(role_id)

    async def buyer(self, role_id: str) -> BuyerRole:
        return await self._buyer(role_id)

    async def seller(self, role_id: str) -> SellerRole:
        return await self._seller(role_id)

    async def _buyer(self, role_id: str) -> BuyerRole:
        role = await self._reader.buyer(role_id)
        if role is None:
            raise RoleNotFoundError(role_id)
        return role

    async def _seller(self, role_id: str) -> SellerRole:
        role = await self._reader.seller(role_id)
        if role is None:
            raise RoleNotFoundError(role_id)
        return role
