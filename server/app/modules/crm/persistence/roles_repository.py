"""Reads buyer and seller roles for the Engine from the existing tables.

Only live rows are listed: an active role of a non-removed organization. Rows are
ordered by organization name then role id, which keeps the keyset cursor stable.
"""

import base64
import json
import uuid
from collections.abc import Sequence
from typing import Final, TypeVar

from pydantic import JsonValue
from sqlalchemy import (
    ColumnElement,
    Numeric,
    Select,
    and_,
    case,
    distinct,
    exists,
    func,
    or_,
    select,
    tuple_,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import InstrumentedAttribute

from app.models import BuyerRole as BuyerRoleRow
from app.models import Organization, User
from app.models import Person as PersonRow
from app.models import SellerRole as SellerRoleRow
from app.modules.crm.domain.roles import (
    BuyerFilterOptions,
    BuyerFilters,
    BuyerRole,
    BuyersPage,
    InvalidCursorError,
    Person,
    Range,
    SellerFilterOptions,
    SellerFilters,
    SellerRole,
    SellersPage,
    SignedInUser,
    TeamMember,
    appetite_signals,
)
from app.modules.crm.persistence.mappers import to_buyer, to_person, to_seller

_UNKNOWN_SIGNALS: Final = "Unknown"

T = TypeVar("T")

_NO_BUYER_OPTIONS: Final = BuyerFilterOptions((), (), ())
_NO_SELLER_OPTIONS: Final = SellerFilterOptions((), ())


def _encode_cursor(name: str, role_id: uuid.UUID) -> str:
    payload = json.dumps({"n": name, "i": str(role_id)}).encode()
    return base64.urlsafe_b64encode(payload).decode()


def _decode_cursor(cursor: str) -> tuple[str, uuid.UUID]:
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        return str(payload["n"]), uuid.UUID(str(payload["i"]))
    except (ValueError, KeyError, TypeError) as exc:
        raise InvalidCursorError(cursor) from exc


def _money(
    column: InstrumentedAttribute[dict[str, JsonValue] | None],
) -> ColumnElement[float | None]:
    """The stored amount, or NULL when missing or not a number, so one malformed
    row never fails the whole query."""
    amount = column["amount"]
    return case((func.jsonb_typeof(amount) == "number", amount.astext.cast(Numeric)), else_=None)


def _in_range(value: ColumnElement[float | None], bounds: Range) -> list[ColumnElement[bool]]:
    """An unknown value only passes an open range."""
    if bounds.is_open:
        return []
    conditions = [value.is_not(None)]
    if bounds.min is not None:
        conditions.append(value >= bounds.min)
    if bounds.max is not None:
        conditions.append(value <= bounds.max)
    return conditions


def _has_item(joined: ColumnElement[str | None], value: str) -> ColumnElement[bool]:
    """A multi-select stored as one ", "-joined text holds `value` as one item."""
    items = func.regexp_split_to_array(joined, r"\s*,\s*")
    return func.array_position(items, value).is_not(None)


def _words(text: str) -> list[str]:
    return text.split()


class PostgresRolesRepository:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def member_by_email(self, email: str) -> SignedInUser | None:
        async with self._sessionmaker() as session:
            stmt = select(User).where(
                func.lower(User.email) == email.lower(), User.active.is_(True)
            )
            user = (await session.execute(stmt.limit(1))).scalar_one_or_none()
        if user is None:
            return None
        return SignedInUser(id=user.attio_id, name=user.name, email=email.lower())

    async def buyer(self, role_id: str) -> BuyerRole | None:
        parsed = _parse_id(role_id)
        if parsed is None:
            return None
        async with self._sessionmaker() as session:
            stmt = _buyer_select().where(*_buyer_live(), BuyerRoleRow.id == parsed)
            row = (await session.execute(stmt)).first()
        return None if row is None else to_buyer(row[0], row[1])

    async def seller(self, role_id: str) -> SellerRole | None:
        parsed = _parse_id(role_id)
        if parsed is None:
            return None
        async with self._sessionmaker() as session:
            stmt = _seller_select().where(*_seller_live(), SellerRoleRow.id == parsed)
            row = (await session.execute(stmt)).first()
            if row is None:
                return None
            contacts = await _org_contacts(session, [row[1].attio_id])
        return to_seller(row[0], row[1], contacts)

    async def buyers_page(
        self, filters: BuyerFilters, cursor: str | None, limit: int
    ) -> BuyersPage:
        conditions = [*_buyer_live(), *_buyer_conditions(filters)]
        async with self._sessionmaker() as session:
            stmt = _buyer_select().where(*conditions)
            if cursor is not None:
                name, role_id = _decode_cursor(cursor)
                stmt = stmt.where(tuple_(Organization.name, BuyerRoleRow.id) > (name, role_id))
            stmt = stmt.order_by(Organization.name, BuyerRoleRow.id).limit(limit + 1)
            fetched = (await session.execute(stmt)).all()
            rows = fetched[:limit]
            # Counts, options and the team come with the first page; later pages carry rows only.
            first = cursor is None
            matched = await _count(session, BuyerRoleRow, conditions) if first else 0
            total = await _count(session, BuyerRoleRow, _buyer_live()) if first else 0
            people = await _buyer_people(session, [role for role, _ in rows])
            users = await _team(session) if first else ()
            options = await _buyer_options(session) if first else _NO_BUYER_OPTIONS
        roles = tuple(to_buyer(role, org) for role, org in rows)
        next_cursor = (
            _encode_cursor(rows[-1][1].name, rows[-1][0].id) if len(fetched) > limit else None
        )
        return BuyersPage(roles, people, users, matched, total, next_cursor, options)

    async def sellers_page(
        self, filters: SellerFilters, cursor: str | None, limit: int
    ) -> SellersPage:
        conditions = [*_seller_live(), *_seller_conditions(filters)]
        async with self._sessionmaker() as session:
            stmt = _seller_select().where(*conditions)
            if cursor is not None:
                name, role_id = _decode_cursor(cursor)
                stmt = stmt.where(tuple_(Organization.name, SellerRoleRow.id) > (name, role_id))
            stmt = stmt.order_by(Organization.name, SellerRoleRow.id).limit(limit + 1)
            fetched = (await session.execute(stmt)).all()
            rows = fetched[:limit]
            first = cursor is None
            matched = await _count(session, SellerRoleRow, conditions) if first else 0
            total = await _count(session, SellerRoleRow, _seller_live()) if first else 0
            contacts = await _org_contacts(session, [org.attio_id for _, org in rows])
            users = await _team(session) if first else ()
            options = await _seller_options(session) if first else _NO_SELLER_OPTIONS
        roles = tuple(to_seller(role, org, contacts) for role, org in rows)
        people = tuple(person for group in contacts.values() for person in group)
        next_cursor = (
            _encode_cursor(rows[-1][1].name, rows[-1][0].id) if len(fetched) > limit else None
        )
        return SellersPage(roles, people, users, matched, total, next_cursor, options)


def _parse_id(role_id: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(role_id)
    except ValueError:
        return None


def _buyer_select() -> Select[tuple[BuyerRoleRow, Organization]]:
    return select(BuyerRoleRow, Organization).join(
        Organization, BuyerRoleRow.org_attio_id == Organization.attio_id
    )


def _seller_select() -> Select[tuple[SellerRoleRow, Organization]]:
    return select(SellerRoleRow, Organization).join(
        Organization, SellerRoleRow.org_attio_id == Organization.attio_id
    )


def _buyer_live() -> list[ColumnElement[bool]]:
    return [
        BuyerRoleRow.is_active.is_(True),
        BuyerRoleRow.removed_at.is_(None),
        Organization.removed_at.is_(None),
    ]


def _seller_live() -> list[ColumnElement[bool]]:
    return [
        SellerRoleRow.is_active.is_(True),
        SellerRoleRow.removed_at.is_(None),
        Organization.removed_at.is_(None),
    ]


async def _count(
    session: AsyncSession,
    role: type[BuyerRoleRow] | type[SellerRoleRow],
    conditions: Sequence[ColumnElement[bool]],
) -> int:
    stmt = (
        select(func.count())
        .select_from(role)
        .join(Organization, role.org_attio_id == Organization.attio_id)
        .where(*conditions)
    )
    return int((await session.execute(stmt)).scalar_one())


def _buyer_conditions(filters: BuyerFilters) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if filters.sectors:
        conditions.append(BuyerRoleRow.target_vertical.in_(filters.sectors))
    if filters.geographies:
        picked = list(filters.geographies)
        conditions.append(
            or_(
                BuyerRoleRow.target_region.overlap(picked),
                BuyerRoleRow.target_country.overlap(picked),
            )
        )
    # A missing check-size bound is open, so such a buyer overlaps any range.
    low, high = _money(BuyerRoleRow.check_size_min), _money(BuyerRoleRow.check_size_max)
    if filters.check_size.max is not None:
        conditions.append(or_(low.is_(None), low <= filters.check_size.max))
    if filters.check_size.min is not None:
        conditions.append(or_(high.is_(None), high >= filters.check_size.min))
    conditions += _in_range(_money(BuyerRoleRow.ebitda_floor), filters.min_ebitda)
    for word in _words(filters.text):
        contact = exists().where(
            PersonRow.attio_id == BuyerRoleRow.key_contact_attio_id,
            PersonRow.removed_at.is_(None),
            PersonRow.name.icontains(word, autoescape=True),
        )
        conditions.append(
            or_(
                Organization.name.icontains(word, autoescape=True),
                BuyerRoleRow.notes.icontains(word, autoescape=True),
                Organization.hq_country.icontains(word, autoescape=True),
                BuyerRoleRow.target_vertical.icontains(word, autoescape=True),
                contact,
            )
        )
    return conditions


def _seller_geography() -> ColumnElement[str | None]:
    return func.coalesce(func.nullif(Organization.region, ""), Organization.hq_country)


def _seller_conditions(filters: SellerFilters) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if filters.sectors:
        conditions.append(SellerRoleRow.sector.overlap(list(filters.sectors)))
    if filters.geographies:
        conditions.append(or_(*(_has_item(_seller_geography(), g) for g in filters.geographies)))
    conditions += _in_range(_money(SellerRoleRow.est_revenue), filters.revenue)
    conditions += _in_range(_money(SellerRoleRow.est_ebitda), filters.ebitda)
    if filters.open_to_selling:
        signals = [s for label in filters.open_to_selling for s in appetite_signals(label)]
        picked = SellerRoleRow.appetite_signal.in_(signals)
        # A seller with no signal recorded counts as Unknown.
        conditions.append(
            or_(picked, SellerRoleRow.appetite_signal.is_(None))
            if _UNKNOWN_SIGNALS in filters.open_to_selling
            else picked
        )
    for word in _words(filters.text):
        contact = exists().where(
            PersonRow.company_attio_id == Organization.attio_id,
            PersonRow.removed_at.is_(None),
            PersonRow.name.icontains(word, autoescape=True),
        )
        conditions.append(
            or_(
                Organization.name.icontains(word, autoescape=True),
                Organization.hq_country.icontains(word, autoescape=True),
                func.array_to_string(SellerRoleRow.sector, " ").icontains(word, autoescape=True),
                contact,
            )
        )
    return conditions


async def _buyer_people(session: AsyncSession, roles: Sequence[BuyerRoleRow]) -> tuple[Person, ...]:
    ids = [r.key_contact_attio_id for r in roles if r.key_contact_attio_id]
    if not ids:
        return ()
    stmt = (
        select(PersonRow, Organization.name)
        .outerjoin(Organization, PersonRow.company_attio_id == Organization.attio_id)
        .where(PersonRow.attio_id.in_(ids), PersonRow.removed_at.is_(None))
        .order_by(PersonRow.name, PersonRow.attio_id)
    )
    rows = (await session.execute(stmt)).all()
    return tuple(to_person(p, org_name or "", "buyer") for p, org_name in rows)


async def _org_contacts(session: AsyncSession, org_ids: Sequence[str]) -> dict[str, list[Person]]:
    if not org_ids:
        return {}
    stmt = (
        select(PersonRow, Organization.name)
        .join(Organization, PersonRow.company_attio_id == Organization.attio_id)
        .where(PersonRow.company_attio_id.in_(org_ids), PersonRow.removed_at.is_(None))
        .order_by(PersonRow.name, PersonRow.attio_id)
    )
    grouped: dict[str, list[Person]] = {}
    for person, org_name in (await session.execute(stmt)).all():
        grouped.setdefault(person.company_attio_id or "", []).append(
            to_person(person, org_name, "target")
        )
    return grouped


async def _team(session: AsyncSession) -> tuple[TeamMember, ...]:
    stmt = select(User).where(User.active.is_(True)).order_by(User.name, User.attio_id)
    return tuple(TeamMember(id=u.attio_id, name=u.name) for u in (await session.scalars(stmt)))


async def _buyer_options(session: AsyncSession) -> BuyerFilterOptions:
    live = and_(*_buyer_live())

    def scoped(column: InstrumentedAttribute[T]) -> Select[tuple[T]]:
        return (
            select(distinct(column))
            .select_from(BuyerRoleRow)
            .join(Organization, BuyerRoleRow.org_attio_id == Organization.attio_id)
            .where(live, column.is_not(None))
        )

    sectors = (await session.execute(scoped(BuyerRoleRow.target_vertical))).scalars()
    regions = (await session.execute(scoped(BuyerRoleRow.target_region))).scalars()
    countries = (await session.execute(scoped(BuyerRoleRow.target_country))).scalars()
    geographies = {g for group in (*regions, *countries) for g in group}
    return BuyerFilterOptions(
        sectors=tuple(sorted(s for s in sectors if s)),
        geographies=tuple(sorted(geographies)),
        # Attio's allowed statuses, which the service adds; the rows hold only the ones in use.
        statuses=(),
    )


async def _seller_options(session: AsyncSession) -> SellerFilterOptions:
    live = and_(*_seller_live())
    base = (
        select(distinct(SellerRoleRow.sector))
        .select_from(SellerRoleRow)
        .join(Organization, SellerRoleRow.org_attio_id == Organization.attio_id)
        .where(live)
    )
    sector_groups = (await session.execute(base)).scalars()
    geography_stmt = (
        select(distinct(_seller_geography()))
        .select_from(SellerRoleRow)
        .join(Organization, SellerRoleRow.org_attio_id == Organization.attio_id)
        .where(live, _seller_geography().is_not(None))
    )
    joined = (await session.execute(geography_stmt)).scalars()
    geographies = {
        item.strip() for text in joined if text for item in text.split(",") if item.strip()
    }
    return SellerFilterOptions(
        sectors=tuple(sorted({s for group in sector_groups for s in group})),
        geographies=tuple(sorted(geographies)),
    )
