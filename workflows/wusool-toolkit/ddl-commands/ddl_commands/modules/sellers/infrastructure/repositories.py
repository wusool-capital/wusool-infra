"""Seller persistence. `add()`/`flush()`/`execute()` only — never `commit()` or
`rollback()`; the caller owns the transaction boundary.
"""

from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from wusool_db.models import Organization, SellerRole

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

    async def get_by_org_attio_id(self, org_attio_id: str) -> SellerRole | None:
        """Used by `/add-seller`'s create path to re-check, inside the write
        transaction, that no seller role was created on this organization
        between the search step and the submission — `UNIQUE(org_attio_id)`
        is the final backstop either way.
        """
        stmt = select(SellerRole).where(SellerRole.org_attio_id == org_attio_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def create(self, org_attio_id: str, **fields) -> SellerRole:
        """Upserts (`ON CONFLICT ... DO NOTHING`) rather than a plain insert
        — with the Attio webhook live, `list-entry.created` for the entry
        this same call just created in Attio can reach
        `attio_sync.upsert.sync_seller_role` and land here first, racing
        this call's own write to the same `UNIQUE(org_attio_id)` row. The
        caller (`CreateSellerUseCase`) tells that apart from a genuine
        pre-existing role by comparing `legacy_entry_id` on whatever this
        returns.
        """
        stmt = (
            pg_insert(SellerRole)
            .values(org_attio_id=org_attio_id, **fields)
            .on_conflict_do_nothing(index_elements=["org_attio_id"])
        )
        await self._session.execute(stmt)
        await self._session.flush()
        role = await self.get_by_org_attio_id(org_attio_id)
        assert role is not None
        return role

    async def search_by_organization_name(self, term: str, limit: int = 10) -> list[SellerRole]:
        """Case-insensitive, typo-tolerant name match — same pg_trgm pattern
        as `BuyerRepository.search_by_organization_name`, reusing the same
        `ix_organizations_name_trgm` GIN index (it's on `organizations.name`,
        not buyer/seller-scoped).
        """
        similarity = func.similarity(Organization.name, term)
        stmt = (
            select(SellerRole)
            .join(Organization, SellerRole.org_attio_id == Organization.attio_id)
            .where(
                or_(
                    Organization.name.ilike(f"%{term}%"),
                    similarity > _TRIGRAM_SIMILARITY_THRESHOLD,
                )
            )
            .options(selectinload(SellerRole.organization))
            .order_by(similarity.desc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def update(self, seller_role_id: str, **fields) -> SellerRole | None:
        role = await self.get_by_id(seller_role_id)
        if role is None:
            return None
        for key, value in fields.items():
            setattr(role, key, value)
        # No ORM `onupdate=` on `updated_at` — set explicitly.
        role.updated_at = datetime.now(UTC)
        await self._session.flush()
        return role
