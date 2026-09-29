"""Buyer persistence. `add()`/`flush()`/`execute()` only — never `commit()` or
`rollback()`; the caller owns the transaction boundary.

Implements `application.ports.buyers.BuyerRepositoryPort`.
"""

from datetime import UTC, datetime
from typing import Unpack

from sqlalchemy import func, literal_column, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import BuyerRole, Organization
from app.modules.ddl_commands.application.ports.buyers import BuyerRoleFields
from app.modules.organizations import org_name_trigram_predicate


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

    async def get_active_by_org_and_vertical(
        self, org_attio_id: str, target_vertical: str | None
    ) -> BuyerRole | None:
        """Used by `DdlCommandsService.create_buyer` to check, inside the write
        transaction, whether this organization already has an *active*
        buyer role for the vertical — an org holds one per vertical, and
        `org_attio_id` isn't unique (an org can hold stale/duplicate rows
        too), so this filters to the one flagged `is_active`.
        """
        stmt = select(BuyerRole).where(
            BuyerRole.org_attio_id == org_attio_id,
            BuyerRole.is_active.is_(True),
            BuyerRole.target_vertical == target_vertical,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def create(self, org_attio_id: str, **fields: Unpack[BuyerRoleFields]) -> BuyerRole:
        """Upserts (`ON CONFLICT (legacy_entry_id) DO NOTHING`) rather than a
        plain insert — with the Attio webhook live, `list-entry.created` for
        the entry this same call just created in Attio can reach
        `attio_sync.upsert.sync_buyer_role` and land here first, racing this
        call's own write to the same `legacy_entry_id` row (the unique
        constraint moved there from `org_attio_id` in the 2026-08-28
        migration — an org can hold several role rows now). `RETURNING`
        tells us directly whether this call's insert won; only on a skipped
        insert (conflict) do we look up the pre-existing winner by
        `legacy_entry_id` — never by `org_attio_id`, which no longer
        identifies a single row.
        """
        stmt = (
            pg_insert(BuyerRole)
            .values(org_attio_id=org_attio_id, **fields)
            .on_conflict_do_nothing(index_elements=["legacy_entry_id"])
            .returning(BuyerRole.id)
        )
        inserted_id = (await self._session.execute(stmt)).scalar_one_or_none()
        await self._session.flush()
        if inserted_id is not None:
            role = await self.get_by_id(str(inserted_id))
        else:
            legacy_entry_id = fields["legacy_entry_id"]
            stmt = select(BuyerRole).where(BuyerRole.legacy_entry_id == legacy_entry_id)
            role = (await self._session.execute(stmt)).scalar_one_or_none()
        assert role is not None
        return role

    async def search_by_organization_name(self, term: str, limit: int = 10) -> list[BuyerRole]:
        """`org_name_trigram_predicate` joined against `organizations`.
        Results are ordered most-similar-first. Filters to `is_active`
        roles only — an org can hold stale/duplicate rows post-migration,
        and `/edit-buyer`'s resolution must never hand the operator an
        inactive duplicate as a pickable candidate indistinguishable from
        the real one. Also excludes orgs Attio no longer has (`removed_at`),
        same reasoning.

        `limit` caps *organizations*, and every matched org contributes all
        its active roles — one per vertical — so the vertical step can list
        them without a second query.
        """
        predicate, similarity = org_name_trigram_predicate(term)
        org_stmt = (
            select(BuyerRole.org_attio_id, func.max(similarity).label("score"))
            .join(Organization, BuyerRole.org_attio_id == Organization.attio_id)
            .where(BuyerRole.is_active.is_(True), Organization.removed_at.is_(None), predicate)
            .group_by(BuyerRole.org_attio_id)
            .order_by(literal_column("score").desc())
            .limit(limit)
        )
        org_ids = [row.org_attio_id for row in (await self._session.execute(org_stmt)).all()]
        if not org_ids:
            return []

        roles_stmt = (
            select(BuyerRole)
            .where(BuyerRole.org_attio_id.in_(org_ids), BuyerRole.is_active.is_(True))
            .options(selectinload(BuyerRole.organization))
        )
        roles = (await self._session.execute(roles_stmt)).scalars().all()
        rank = {org_id: i for i, org_id in enumerate(org_ids)}
        return sorted(roles, key=lambda r: (rank[r.org_attio_id], r.target_vertical or ""))

    async def update(
        self, buyer_role_id: str, **fields: Unpack[BuyerRoleFields]
    ) -> BuyerRole | None:
        role = await self.get_by_id(buyer_role_id)
        if role is None:
            return None
        for key, value in fields.items():
            setattr(role, key, value)
        # No ORM `onupdate=` on `updated_at` — set explicitly.
        role.updated_at = datetime.now(UTC)
        await self._session.flush()
        return role
