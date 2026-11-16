"""The use cases behind the Engine's buyer and seller pages."""

from collections.abc import Sequence
from dataclasses import replace

from app.modules.crm.application.ports.roles import RolesReaderPort, RoleWriterPort
from app.modules.crm.domain.roles import (
    BuyerChanges,
    BuyerFilters,
    BuyerRole,
    BuyersPage,
    Detail,
    DetailValue,
    FieldDef,
    InvalidRoleFieldsError,
    NewBuyer,
    NewSeller,
    RoleAlreadyExistsError,
    RoleNotFoundError,
    SellerChanges,
    SellerFilters,
    SellerRole,
    SellersPage,
    SignedInUser,
    StaleRoleError,
    split_geographies,
)

MAX_PAGE_SIZE = 100


# Read-then-write, not atomic: the write goes to Attio first, then Postgres.
def _same_version(etag: str, if_match: str) -> bool:
    # Entity tags travel quoted, and a proxy may mark them weak.
    return etag == if_match.removeprefix("W/").strip('"')


def _is_empty(value: DetailValue) -> bool:
    return value is None or value == "" or value == ()


def _detail_problems(details: Sequence[Detail], fields: Sequence[FieldDef]) -> list[str]:
    labels = {field.key: field.label for field in fields}
    clearable = {field.key for field in fields if field.clearable}
    problems = [
        f"{d.key} is not a field the Engine can set" for d in details if d.key not in labels
    ]
    problems += [
        f"{labels[d.key]} can't be emptied here, only changed. Clear it in Attio"
        for d in details
        if d.key in labels and d.key not in clearable and _is_empty(d.value)
    ]
    keys = [d.key for d in details]
    problems += [f"{key} was sent twice" for key in sorted({k for k in keys if keys.count(k) > 1})]
    return problems


class CrmService:
    def __init__(self, reader: RolesReaderPort, writer: RoleWriterPort) -> None:
        self._reader = reader
        self._writer = writer

    async def sign_in(self, email: str) -> SignedInUser | None:
        return await self._reader.member_by_email(email)

    async def buyers(self, filters: BuyerFilters, cursor: str | None, limit: int) -> BuyersPage:
        page = await self._reader.buyers_page(filters, cursor, min(limit, MAX_PAGE_SIZE))
        if cursor is not None:
            return page
        # The rows only hold values in use; the form needs everything Attio allows.
        options = replace(
            page.options,
            statuses=self._writer.buyer_statuses(),
            regions=self._writer.buyer_regions(),
            countries=self._writer.buyer_countries(),
            hq_countries=self._writer.hq_countries(),
            sector_choices=self._writer.buyer_sectors(),
            fields=self._writer.buyer_fields(),
        )
        return replace(page, options=options)

    async def sellers(self, filters: SellerFilters, cursor: str | None, limit: int) -> SellersPage:
        page = await self._reader.sellers_page(filters, cursor, min(limit, MAX_PAGE_SIZE))
        if cursor is not None:
            return page
        options = replace(
            page.options,
            sector_choices=self._writer.seller_sectors(),
            hq_countries=self._writer.hq_countries(),
            appetite_signals=self._writer.appetite_signals(),
            fields=self._writer.seller_fields(),
        )
        return replace(page, options=options)

    async def add_seller(self, user: SignedInUser, seller: NewSeller) -> SellerRole:
        self._refuse(_detail_problems(seller.details, self._writer.seller_fields()))
        outcome, role_id = await self._writer.add_seller(seller, requested_by=user.id)
        if outcome == "existing":
            raise RoleAlreadyExistsError(role_id, "seller")
        return await self._seller(role_id)

    async def add_buyer(self, user: SignedInUser, buyer: NewBuyer) -> BuyerRole:
        self._check_geographies(buyer.geographies, ())
        self._refuse(_detail_problems(buyer.details, self._writer.buyer_fields()))
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
        if "geographies" in changes.sent:
            self._check_geographies(changes.geographies, current.geographies)
        self._refuse(
            [
                *_detail_problems(changes.details, self._writer.buyer_fields()),
            ]
        )
        await self._writer.edit_buyer(role_id, changes, requested_by=user.id)
        return await self._buyer(role_id)

    async def edit_seller(
        self, user: SignedInUser, role_id: str, changes: SellerChanges, if_match: str
    ) -> SellerRole:
        current = await self._seller(role_id)
        if not _same_version(current.etag, if_match):
            raise StaleRoleError(role_id)
        self._refuse(
            [
                *_detail_problems(changes.details, self._writer.seller_fields()),
            ]
        )
        await self._writer.edit_seller(role_id, changes, requested_by=user.id)
        return await self._seller(role_id)

    @staticmethod
    def _refuse(problems: Sequence[str]) -> None:
        if problems:
            raise InvalidRoleFieldsError(tuple(problems))

    def _check_geographies(self, picked: Sequence[str], current: Sequence[str]) -> None:
        regions, countries = self._writer.buyer_regions(), self._writer.buyer_countries()
        split = split_geographies(picked, regions, countries)
        problems = [f"{name} is not a region or country Attio allows" for name in split.unknown]
        # Attio's edit path cannot empty a multi-select, so a group that has values must keep one.
        held = split_geographies(current, regions, countries)
        if held.regions and not split.regions:
            problems.append("Keep at least one region, or clear them in Attio")
        if held.countries and not split.countries:
            problems.append("Keep at least one country, or clear them in Attio")
        if problems:
            raise InvalidRoleFieldsError(tuple(problems))

    async def buyer(self, role_id: str) -> BuyerRole:
        role = await self._buyer(role_id)
        return replace(role, details=await self._writer.record_details("buyer", role_id))

    async def seller(self, role_id: str) -> SellerRole:
        role = await self._seller(role_id)
        return replace(role, details=await self._writer.record_details("seller", role_id))

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
