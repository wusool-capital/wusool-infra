"""Seller persistence. `add()`/`flush()`/`execute()` only — never `commit()` or
`rollback()`; the caller owns the transaction boundary.

Implements `application.ports.sellers.SellerRepositoryPort` — every public
method returns `SellerCandidate` (domain), mapped from the ORM row here so
`app.models.SellerRole` never crosses the Port boundary.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import SellerRole
from app.modules.matching_engine.domain.sellers import SellerCandidate
from app.modules.matching_engine.persistence.mappers import to_seller_candidate


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

    async def get_eligible_sellers(self, limit: int = 50, offset: int = 0) -> list[SellerCandidate]:
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
        roles = (await self._session.execute(stmt)).scalars().all()
        return [to_seller_candidate(role) for role in roles]

    async def get_structured_fields(self, seller_role_id: str) -> SellerCandidate | None:
        """Returns the seller's requirement-relevant fields — est_revenue/
        est_ebitda/valuation_low/mid/high already live directly on this
        table; there is no separate `seller_profiles` table (PRD.md §3.3
        describes a versioned one; never implemented).
        """
        return await self.get_by_id(seller_role_id)
