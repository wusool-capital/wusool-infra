"""Buyer persistence. `add()`/`flush()`/`execute()` only — never `commit()` or
`rollback()`; the caller owns the transaction boundary.
"""

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from wusool_db.models import BuyerRole, Organization

# pg_trgm's own `%` similarity operator depends on a session-level GUC
# (pg_trgm.similarity_threshold); comparing func.similarity(...) against an
# explicit constant is equivalent to that operator's own default and doesn't
# depend on session state.
_TRIGRAM_SIMILARITY_THRESHOLD = 0.3


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
        """Case-insensitive, typo-tolerant name match.

        `pg_trgm` (001_extensions.sql, GIN index in
        007_org_name_trgm_index.sql) ranks by trigram similarity, so a
        misspelled name still surfaces a match — but the plain `ILIKE`
        substring match is always included too (`OR`), so an exact/partial
        typed name never regresses to relying on a similarity score.
        Results are ordered most-similar-first.
        """
        similarity = func.similarity(Organization.name, term)
        stmt = (
            select(BuyerRole)
            .join(Organization, BuyerRole.org_attio_id == Organization.attio_id)
            .where(
                or_(
                    Organization.name.ilike(f"%{term}%"),
                    similarity > _TRIGRAM_SIMILARITY_THRESHOLD,
                )
            )
            .options(selectinload(BuyerRole.organization))
            .order_by(similarity.desc())
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
