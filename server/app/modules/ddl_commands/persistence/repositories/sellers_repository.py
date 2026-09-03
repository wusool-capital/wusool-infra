"""Seller persistence. `add()`/`flush()`/`execute()` only — never `commit()` or
`rollback()`; the caller owns the transaction boundary.

Implements `application.ports.sellers.SellerRepositoryPort`.
"""

from datetime import UTC, datetime
from typing import Unpack

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Organization, SellerRole
from app.modules.ddl_commands.application.ports.sellers import SellerRoleFields

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
        """Used by `CreateSellerUseCase` to check, inside the write
        transaction, whether this organization already has an *active*
        seller role — `org_attio_id` stopped being unique in the 2026-08-28
        migration (an org can hold stale/duplicate rows too), so this
        filters to the one flagged `is_active`, same truthy convention as
        `handle_organization_selection_submission`'s
        `any(r.is_active for r in roles)`.
        """
        stmt = select(SellerRole).where(
            SellerRole.org_attio_id == org_attio_id, SellerRole.is_active.is_(True)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def create(self, org_attio_id: str, **fields: Unpack[SellerRoleFields]) -> SellerRole:
        """Upserts (`ON CONFLICT (legacy_entry_id) DO NOTHING`) rather than a
        plain insert — with the Attio webhook live, `list-entry.created` for
        the entry this same call just created in Attio can reach
        `attio_sync.upsert.sync_seller_role` and land here first, racing
        this call's own write to the same `legacy_entry_id` row (the unique
        constraint moved there from `org_attio_id` in the 2026-08-28
        migration — an org can hold several role rows now). `RETURNING`
        tells us directly whether this call's insert won; only on a skipped
        insert (conflict) do we look up the pre-existing winner by
        `legacy_entry_id` — never by `org_attio_id`, which no longer
        identifies a single row.
        """
        stmt = (
            pg_insert(SellerRole)
            .values(org_attio_id=org_attio_id, **fields)
            .on_conflict_do_nothing(index_elements=["legacy_entry_id"])
            .returning(SellerRole.id)
        )
        inserted_id = (await self._session.execute(stmt)).scalar_one_or_none()
        await self._session.flush()
        if inserted_id is not None:
            role = await self.get_by_id(str(inserted_id))
        else:
            legacy_entry_id = fields["legacy_entry_id"]
            stmt = select(SellerRole).where(SellerRole.legacy_entry_id == legacy_entry_id)
            role = (await self._session.execute(stmt)).scalar_one_or_none()
        assert role is not None
        return role

    async def search_by_organization_name(self, term: str, limit: int = 10) -> list[SellerRole]:
        """Case-insensitive, typo-tolerant name match — same pg_trgm pattern
        as `BuyerRepository.search_by_organization_name`, reusing the same
        `ix_organizations_name_trgm` GIN index (it's on `organizations.name`,
        not buyer/seller-scoped). Filters to `is_active` roles only — an
        org can hold stale/duplicate rows post-migration, and
        `/edit-seller`'s resolution must never hand the operator an
        inactive duplicate as a pickable candidate indistinguishable from
        the real one.
        """
        similarity = func.similarity(Organization.name, term)
        stmt = (
            select(SellerRole)
            .join(Organization, SellerRole.org_attio_id == Organization.attio_id)
            .where(
                SellerRole.is_active.is_(True),
                or_(
                    Organization.name.ilike(f"%{term}%"),
                    similarity > _TRIGRAM_SIMILARITY_THRESHOLD,
                ),
            )
            .options(selectinload(SellerRole.organization))
            .order_by(similarity.desc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def update(
        self, seller_role_id: str, **fields: Unpack[SellerRoleFields]
    ) -> SellerRole | None:
        role = await self.get_by_id(seller_role_id)
        if role is None:
            return None
        for key, value in fields.items():
            setattr(role, key, value)
        # No ORM `onupdate=` on `updated_at` — set explicitly.
        role.updated_at = datetime.now(UTC)
        await self._session.flush()
        return role
