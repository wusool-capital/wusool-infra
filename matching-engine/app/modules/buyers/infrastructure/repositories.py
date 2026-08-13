"""Buyer persistence. `add()`/`flush()`/`execute()` only — never `commit()` or
`rollback()`; the caller owns the transaction boundary.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.buyers.infrastructure.models import BuyerRole
from app.shared.database.models import Organization


class BuyerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, buyer_role_id: str) -> BuyerRole | None:
        return await self._session.get(BuyerRole, buyer_role_id)

    async def get_with_organization(self, buyer_role_id: str) -> BuyerRole | None:
        stmt = (
            select(BuyerRole)
            .where(BuyerRole.id == buyer_role_id)
            .options(selectinload(BuyerRole.organization), selectinload(BuyerRole.key_contact))
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def search_by_organization_name(self, term: str, limit: int = 10) -> list[BuyerRole]:
        """Case-insensitive, partial name match.

        No `pg_trgm` — it isn't enabled anywhere in this database, and this
        phase must not add extensions. This is a plain `ILIKE` substring
        match; swap in trigram similarity later behind this same method if
        the extension is ever enabled.
        """
        stmt = (
            select(BuyerRole)
            .join(Organization, BuyerRole.org_attio_id == Organization.attio_id)
            .where(Organization.name.ilike(f"%{term}%"))
            .options(selectinload(BuyerRole.organization))
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_requirement_profile(self, buyer_role_id: str) -> BuyerRole | None:
        """Returns the `BuyerRole` row itself.

        There is no separate versioned `buyer_requirement_profiles` table in
        the real schema (PRD.md §3.3 describes one; never implemented) —
        `buyer_roles`'s own fields (check_size_min/max, ebitda_floor,
        ev_ceiling, investment_strategy, notes, ...) are the entirety of the
        buyer's requirement data today.
        """
        return await self.get_by_id(buyer_role_id)
