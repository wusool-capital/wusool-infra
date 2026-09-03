"""Buyer persistence. `add()`/`flush()`/`execute()` only — never `commit()` or
`rollback()`; the caller owns the transaction boundary.

Implements `application.ports.buyers.BuyerRepositoryPort`.
"""

from datetime import UTC, datetime
from typing import Unpack

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import BuyerRole, Organization
from app.modules.ddl_commands.application.ports.buyers import BuyerRoleFields

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

    async def get_by_org_attio_id(self, org_attio_id: str) -> BuyerRole | None:
        """Used by `CreateBuyerUseCase` to check, inside the write
        transaction, whether this organization already has an *active*
        buyer role — `org_attio_id` stopped being unique in the 2026-08-28
        migration (an org can hold stale/duplicate rows too), so this
        filters to the one flagged `is_active`, same truthy convention as
        `handle_organization_selection_submission`'s
        `any(r.is_active for r in roles)`.
        """
        stmt = select(BuyerRole).where(
            BuyerRole.org_attio_id == org_attio_id, BuyerRole.is_active.is_(True)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

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
        """Case-insensitive, typo-tolerant name match.

        `pg_trgm` (001_extensions.sql, GIN index in 007_org_name_trgm_index.sql)
        ranks by trigram similarity, so a misspelled name still surfaces a
        match — but the plain `ILIKE` substring match is always included too
        (`OR`), so an exact/partial typed name never regresses to relying on
        a similarity score. Results are ordered most-similar-first. Filters
        to `is_active` roles only — an org can hold stale/duplicate rows
        post-migration, and `/edit-buyer`'s resolution must never hand the
        operator an inactive duplicate as a pickable candidate
        indistinguishable from the real one.
        """
        similarity = func.similarity(Organization.name, term)
        stmt = (
            select(BuyerRole)
            .join(Organization, BuyerRole.org_attio_id == Organization.attio_id)
            .where(
                BuyerRole.is_active.is_(True),
                or_(
                    Organization.name.ilike(f"%{term}%"),
                    similarity > _TRIGRAM_SIMILARITY_THRESHOLD,
                ),
            )
            .options(selectinload(BuyerRole.organization))
            .order_by(similarity.desc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

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
