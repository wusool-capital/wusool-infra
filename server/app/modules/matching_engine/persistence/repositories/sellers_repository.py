"""Seller persistence. `add()`/`flush()`/`execute()` only — never `commit()` or
`rollback()`; the caller owns the transaction boundary.

Implements `application.ports.sellers.SellerRepositoryPort` — every public
method returns `SellerCandidate` (domain), mapped from the ORM row here so
`app.models.SellerRole` never crosses the Port boundary.
"""

import logging
from decimal import Decimal

from sqlalchemy import (
    ColumnElement,
    Numeric,
    SQLColumnExpression,
    and_,
    case,
    exists,
    func,
    literal,
    or_,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Organization, SellerRole
from app.modules.matching_engine.domain.matching.narrowing import CandidateNarrowing
from app.modules.matching_engine.domain.sellers import SellerCandidate
from app.modules.matching_engine.persistence.mappers import to_seller_candidate
from app.modules.utilities.domain.json_types import JsonObject

logger = logging.getLogger(__name__)

# A backstop, not a working limit: narrowing should keep results well under it.
MAX_ELIGIBLE_SELLERS = 5000


def _lower_elements_in(
    array: SQLColumnExpression[list[str]], values: frozenset[str]
) -> ColumnElement[bool]:
    element = func.unnest(array).column_valued("element")
    return exists(select(literal(1)).where(func.lower(element).in_(values)))


def _is_nonblank(text: SQLColumnExpression[str | None]) -> ColumnElement[bool]:
    return func.btrim(func.coalesce(text, "")) != ""


def _usd_amount(column: SQLColumnExpression[JsonObject | None]) -> ColumnElement[Decimal | None]:
    """NULL for anything that isn't a plain USD number, so one malformed JSONB
    row passes through instead of failing the whole query on a bad cast."""
    money = column
    currency = money["currency"].astext
    return case(
        (
            and_(
                func.jsonb_typeof(money["amount"]) == "number",
                or_(currency.is_(None), currency == "USD"),
            ),
            money["amount"].astext.cast(Numeric),
        ),
        else_=None,
    )


def _vertical_predicate(vertical: str) -> ColumnElement[bool]:
    has_data = or_(
        func.coalesce(func.cardinality(SellerRole.sector), 0) > 0,
        func.coalesce(func.cardinality(Organization.sector_focus), 0) > 0,
    )
    matches = or_(
        _lower_elements_in(SellerRole.sector, frozenset({vertical})),
        _lower_elements_in(Organization.sector_focus, frozenset({vertical})),
    )
    return or_(~has_data, matches)


def _geography_predicate(narrowing: CandidateNarrowing) -> ColumnElement[bool]:
    hq_countries = func.regexp_split_to_array(
        func.coalesce(Organization.hq_country, ""), r"\s*,\s*"
    )
    has_data = or_(
        _is_nonblank(Organization.region),
        _is_nonblank(Organization.hq_country),
        func.coalesce(func.cardinality(Organization.geographic_focus), 0) > 0,
    )
    matches = or_(
        func.lower(func.coalesce(Organization.region, "")).in_(narrowing.regions),
        _lower_elements_in(hq_countries, narrowing.countries),
        _lower_elements_in(Organization.geographic_focus, narrowing.countries | narrowing.regions),
    )
    return or_(~has_data, matches)


def _ev_ceiling_predicate(ev_ceiling: float) -> ColumnElement[bool]:
    low = _usd_amount(SellerRole.valuation_low)
    return or_(low.is_(None), low <= ev_ceiling)


class SellerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, seller_role_id: str) -> SellerCandidate | None:
        stmt = (
            select(SellerRole)
            .where(SellerRole.id == seller_role_id)
            .options(selectinload(SellerRole.organization))
        )
        role = (await self._session.execute(stmt)).scalar_one_or_none()
        return to_seller_candidate(role) if role else None

    async def get_with_organization(self, seller_role_id: str) -> SellerCandidate | None:
        stmt = (
            select(SellerRole)
            .where(SellerRole.id == seller_role_id)
            .options(selectinload(SellerRole.organization))
        )
        role = (await self._session.execute(stmt)).scalar_one_or_none()
        return to_seller_candidate(role) if role else None

    async def get_eligible_sellers(
        self, narrowing: CandidateNarrowing, limit: int = MAX_ELIGIBLE_SELLERS
    ) -> list[SellerCandidate]:
        """ "Eligible" is lifecycle state (`is_active`, soft-deletes) plus the
        buyer's `narrowing` on vertical, geography and EV ceiling. A seller
        with no data for a narrowed dimension always passes it — the same
        missing-data rule as `apply_structured_filters`, which still runs
        after this for the requirement-level filters.
        """
        conditions: list[ColumnElement[bool]] = [
            SellerRole.is_active.is_(True),
            SellerRole.removed_at.is_(None),
            Organization.removed_at.is_(None),
        ]
        if narrowing.vertical:
            conditions.append(_vertical_predicate(narrowing.vertical))
        if narrowing.narrows_geography:
            conditions.append(_geography_predicate(narrowing))
        if narrowing.ev_ceiling is not None:
            conditions.append(_ev_ceiling_predicate(narrowing.ev_ceiling))

        stmt = (
            select(SellerRole)
            .join(Organization, SellerRole.org_attio_id == Organization.attio_id)
            .where(*conditions)
            .options(selectinload(SellerRole.organization))
            .order_by(SellerRole.id)
            .limit(limit)
        )
        roles = (await self._session.execute(stmt)).scalars().all()
        if len(roles) == limit:
            logger.warning("eligible_sellers_cap_hit", extra={"limit": limit})
        return [to_seller_candidate(role) for role in roles]

    async def get_structured_fields(self, seller_role_id: str) -> SellerCandidate | None:
        """Returns the seller's requirement-relevant fields — est_revenue/
        est_ebitda/valuation_low/mid/high already live directly on this
        table; there is no separate `seller_profiles` table (PRD.md §3.3
        describes a versioned one; never implemented).
        """
        return await self.get_by_id(seller_role_id)
