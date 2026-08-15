"""Seller persistence. `add()`/`flush()`/`execute()` only — never `commit()` or
`rollback()`; the caller owns the transaction boundary.
"""

from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.sellers.infrastructure.models import SellerRole
from app.shared.database.models import Organization

# Same rationale as BuyerRepository's constant — see that file's comment.
_TRIGRAM_SIMILARITY_THRESHOLD = 0.3


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
        """Excludes archived rows — this bot has no matching pipeline of its
        own, but keeping the same filter here means this method's meaning
        stays consistent if it's ever reused.
        """
        stmt = (
            select(SellerRole)
            .where(SellerRole.archived_at.is_(None))
            .options(selectinload(SellerRole.organization))
            .limit(limit)
            .offset(offset)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def search_by_organization_name(
        self, term: str, limit: int = 10, *, include_archived: bool = False
    ) -> list[SellerRole]:
        """Case-insensitive, typo-tolerant name match — same pg_trgm pattern
        as `BuyerRepository.search_by_organization_name`, reusing the same
        `ix_organizations_name_trgm` GIN index (it's on `organizations.name`,
        not buyer/seller-scoped).

        `include_archived=False` (default) excludes archived rows. Only
        `/edit-seller`'s resolution passes `include_archived=True`, so an
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
            conditions.append(SellerRole.archived_at.is_(None))
        stmt = (
            select(SellerRole)
            .join(Organization, SellerRole.org_attio_id == Organization.attio_id)
            .where(*conditions)
            .options(selectinload(SellerRole.organization))
            .order_by(similarity.desc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def update(
        self, seller_role_id: str, actor_user_id: str, **fields
    ) -> SellerRole | None:
        role = await self.get_by_id(seller_role_id)
        if role is None:
            return None
        for key, value in fields.items():
            setattr(role, key, value)
        # No ORM `onupdate=` on `updated_at` — set explicitly.
        role.bot_managed_at = role.updated_at = datetime.now(UTC)
        role.bot_managed_by = actor_user_id
        await self._session.flush()
        return role

    async def archive(self, seller_role_id: str, actor_user_id: str) -> SellerRole | None:
        role = await self.get_by_id(seller_role_id)
        if role is None:
            return None
        role.archived_at = role.bot_managed_at = role.updated_at = datetime.now(UTC)
        role.bot_managed_by = actor_user_id
        await self._session.flush()
        return role
