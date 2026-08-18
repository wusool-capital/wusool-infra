"""Seller persistence. `add()`/`flush()`/`execute()` only — never `commit()` or
`rollback()`; the caller owns the transaction boundary.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from wusool_db.models import SellerRole


class SellerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, seller_role_id: str) -> SellerRole | None:
        return await self._session.get(SellerRole, seller_role_id)

    async def get_with_organization(self, seller_role_id: str) -> SellerRole | None:
        stmt = (
            select(SellerRole)
            .where(SellerRole.id == seller_role_id)
            .options(selectinload(SellerRole.organization))
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_eligible_sellers(self, limit: int = 50, offset: int = 0) -> list[SellerRole]:
        """ "Eligible" has no schema-level flag today — returns `seller_roles`
        joined to `organizations`, unfiltered. Real eligibility filtering is
        Phase 3 business logic, not a repository concern.
        """
        stmt = (
            select(SellerRole)
            .options(selectinload(SellerRole.organization))
            .limit(limit)
            .offset(offset)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_structured_fields(self, seller_role_id: str) -> SellerRole | None:
        """Returns the `SellerRole` row itself — est_revenue/est_ebitda/
        valuation_low/mid/high already live directly on this table; there is
        no separate `seller_profiles` table (PRD.md §3.3 describes a
        versioned one; never implemented).
        """
        return await self.get_by_id(seller_role_id)
