"""Seller persistence. `add()`/`flush()`/`execute()` only — never `commit()` or
`rollback()`; the caller owns the transaction boundary.

Implements `application.ports.sellers.SellerRepositoryPort`.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Unpack

from sqlalchemy import ColumnElement, and_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager, selectinload

from app.models import Organization, SellerRole
from app.modules.ddl_commands.application.ports.sellers import SellerFilters, SellerRoleFields
from app.modules.ddl_commands.persistence.repositories.filters import joined_text_has
from app.modules.organizations import org_name_trigram_predicate


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

    async def get_many_with_organization(self, seller_role_ids: Sequence[str]) -> list[SellerRole]:
        """Unknown ids are simply absent from the result."""
        stmt = (
            select(SellerRole)
            .where(SellerRole.id.in_(seller_role_ids))
            .options(selectinload(SellerRole.organization))
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_by_org_attio_id(self, org_attio_id: str) -> SellerRole | None:
        """Used by `DdlCommandsService.create_seller` to check, inside the write
        transaction, whether this organization already has an *active*
        seller role — `org_attio_id` stopped being unique in the 2026-08-28
        migration (an org can hold stale/duplicate rows too), so this
        filters to the one flagged `is_active`, same truthy convention as
        `handle_organization_selection_submission`'s
        `any(r.is_active for r in roles)`.
        """
        stmt = (
            select(SellerRole)
            .where(SellerRole.org_attio_id == org_attio_id, SellerRole.is_active.is_(True))
            .order_by(SellerRole.created_at.desc())
        )
        return (await self._session.execute(stmt)).scalars().first()

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
        """`org_name_trigram_predicate` joined against `organizations`,
        reusing the same `ix_organizations_name_trgm` GIN index (it's on
        `organizations.name`, not buyer/seller-scoped). Filters to
        `is_active` roles only — an org can hold stale/duplicate rows
        post-migration, and `/edit-seller`'s resolution must never hand the
        operator an inactive duplicate as a pickable candidate
        indistinguishable from the real one. Also excludes orgs Attio no
        longer has (`removed_at`), same reasoning.
        """
        predicate, similarity = org_name_trigram_predicate(term)
        stmt = (
            select(SellerRole)
            .join(Organization, SellerRole.org_attio_id == Organization.attio_id)
            .where(SellerRole.is_active.is_(True), Organization.removed_at.is_(None), predicate)
            .options(selectinload(SellerRole.organization))
            .order_by(similarity.desc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_filtered(
        self, filters: SellerFilters, limit: int, offset: int = 0
    ) -> list[SellerRole]:
        """Active roles of live organizations, ordered by organization name then id."""
        conditions: list[ColumnElement[bool]] = [
            SellerRole.is_active.is_(True),
            SellerRole.removed_at.is_(None),
            Organization.removed_at.is_(None),
        ]
        if filters.sector is not None:
            conditions.append(Organization.sector_focus.contains([filters.sector]))
        if filters.hq_country is not None:
            conditions.append(joined_text_has(Organization.hq_country, filters.hq_country))
        if filters.region is not None:
            conditions.append(joined_text_has(Organization.region, filters.region))
        if filters.relationship_status is not None:
            conditions.append(SellerRole.relationship_status == filters.relationship_status)
        if filters.outreach_tier is not None:
            conditions.append(SellerRole.outreach_tier == filters.outreach_tier)
        stmt = (
            select(SellerRole)
            .join(Organization, SellerRole.org_attio_id == Organization.attio_id)
            .where(and_(*conditions))
            .options(contains_eager(SellerRole.organization))
            .order_by(Organization.name, SellerRole.id)
            .limit(limit)
            .offset(offset)
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
