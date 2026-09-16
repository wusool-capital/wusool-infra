"""Buyer persistence. `add()`/`flush()`/`execute()` only — never `commit()` or
`rollback()`; the caller owns the transaction boundary.

Implements `application.ports.buyers.BuyerRepositoryPort` — every public
method returns `BuyerContext` (domain), mapped from the ORM row here so
`app.models.BuyerRole` never crosses the Port boundary.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import BuyerRole, Organization
from app.modules.matching_engine.domain.buyers import BuyerContext
from app.modules.matching_engine.persistence.mappers import to_buyer_context
from app.modules.organizations import org_name_trigram_predicate


class BuyerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _get_by_id_row(self, buyer_role_id: str) -> BuyerRole | None:
        stmt = (
            select(BuyerRole)
            .where(BuyerRole.id == buyer_role_id)
            .options(selectinload(BuyerRole.organization))
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_id(self, buyer_role_id: str) -> BuyerContext | None:
        role = await self._get_by_id_row(buyer_role_id)
        return to_buyer_context(role) if role else None

    async def get_with_organization(self, buyer_role_id: str) -> BuyerContext | None:
        stmt = (
            select(BuyerRole)
            .where(BuyerRole.id == buyer_role_id)
            .options(selectinload(BuyerRole.organization), selectinload(BuyerRole.key_contact))
        )
        role = (await self._session.execute(stmt)).scalar_one_or_none()
        return to_buyer_context(role) if role else None

    async def search_by_organization_name(self, term: str, limit: int = 10) -> list[BuyerContext]:
        """`org_name_trigram_predicate` joined against `organizations`.
        Results are ordered most-similar-first. Filters to `is_active`
        roles only — an org can hold stale/duplicate rows post-migration,
        and this search must never hand `/find-match` an inactive
        duplicate role indistinguishable from the real one (same
        reasoning as `ddl_commands.BuyerRepository`'s own version of this
        method). Also excludes orgs Attio no longer has (`removed_at`),
        same reasoning.
        """
        predicate, similarity = org_name_trigram_predicate(term)
        stmt = (
            select(BuyerRole)
            .join(Organization, BuyerRole.org_attio_id == Organization.attio_id)
            .where(BuyerRole.is_active.is_(True), Organization.removed_at.is_(None), predicate)
            .options(selectinload(BuyerRole.organization))
            .order_by(similarity.desc())
            .limit(limit)
        )
        roles = (await self._session.execute(stmt)).scalars().all()
        return [to_buyer_context(role) for role in roles]

    async def get_requirement_profile(self, buyer_role_id: str) -> BuyerContext | None:
        """Returns the buyer's requirement-relevant fields.

        There is no separate versioned `buyer_requirement_profiles` table in
        the real schema (PRD.md §3.3 describes one; never implemented) —
        `buyer_roles`'s own fields (check_size_min/max, ebitda_floor,
        ev_ceiling, investment_strategy, notes, ...) are the entirety of the
        buyer's requirement data today.
        """
        return await self.get_by_id(buyer_role_id)
