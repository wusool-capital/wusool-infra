"""Buyer persistence. `add()`/`flush()`/`execute()` only — never `commit()` or
`rollback()`; the caller owns the transaction boundary.
"""

from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.buyers.infrastructure.models import BuyerRole
from app.shared.database.models import Organization

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
            .options(selectinload(BuyerRole.organization))
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def search_by_organization_name(
        self, term: str, limit: int = 10, *, include_archived: bool = False
    ) -> list[BuyerRole]:
        """Case-insensitive, typo-tolerant name match.

        `pg_trgm` (001_extensions.sql, GIN index in 007_org_name_trgm_index.sql)
        ranks by trigram similarity, so a misspelled name still surfaces a
        match — but the plain `ILIKE` substring match is always included too
        (`OR`), so an exact/partial typed name never regresses to relying on
        a similarity score. Results are ordered most-similar-first.

        `include_archived=False` (default) excludes archived rows — this is
        what keeps a removed buyer out of new matching/lookup. Only
        `/edit-buyer`'s resolution passes `include_archived=True`, so an
        archived row can be found and restored.
        """
        similarity = func.similarity(Organization.name, term)
        conditions = [
            or_(
                Organization.name.ilike(f"%{term}%"),
                similarity > _TRIGRAM_SIMILARITY_THRESHOLD,
            )
        ]
        if not include_archived:
            conditions.append(BuyerRole.archived_at.is_(None))
        stmt = (
            select(BuyerRole)
            .join(Organization, BuyerRole.org_attio_id == Organization.attio_id)
            .where(*conditions)
            .options(selectinload(BuyerRole.organization))
            .order_by(similarity.desc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def update(
        self, buyer_role_id: str, actor_user_id: str, **fields
    ) -> BuyerRole | None:
        role = await self.get_by_id(buyer_role_id)
        if role is None:
            return None
        for key, value in fields.items():
            setattr(role, key, value)
        # No ORM `onupdate=` on `updated_at` — set explicitly.
        role.bot_managed_at = role.updated_at = datetime.now(UTC)
        role.bot_managed_by = actor_user_id
        await self._session.flush()
        return role

    async def archive(self, buyer_role_id: str, actor_user_id: str) -> BuyerRole | None:
        role = await self.get_by_id(buyer_role_id)
        if role is None:
            return None
        role.archived_at = role.bot_managed_at = role.updated_at = datetime.now(UTC)
        role.bot_managed_by = actor_user_id
        await self._session.flush()
        return role
