"""Organization persistence — read/write, shared by `/edit-seller`/
`/edit-buyer` (an edit can touch org-level fields alongside role fields) and
`/add-seller`/`/add-buyer` (`search_by_name` powers the search-before-create
step, `create` is only ever called after the org's real Attio record already
exists — see `ddl_commands/README.md`, "Why Attio-first"). `add()`/`flush()`/
`execute()` only — never `commit()`/`rollback()`; the caller owns the
transaction boundary.
"""

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Organization

# Same rationale as SellerRepository's/BuyerRepository's constant.
_TRIGRAM_SIMILARITY_THRESHOLD = 0.3


class OrganizationRepository:  # implements OrganizationRepositoryPort
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, attio_id: str) -> Organization | None:
        return await self._session.get(Organization, attio_id)

    async def get_by_id_with_roles(self, attio_id: str) -> Organization | None:
        """Like `get_by_id`, but eager-loads `seller_roles`/`buyer_roles` — for
        the org-selection step of `/add-seller`/`/add-buyer`, which needs to
        re-check (never trusting the Slack payload) whether the freshly
        re-loaded org already has the role kind being added.
        """
        stmt = (
            select(Organization)
            .where(Organization.attio_id == attio_id)
            .options(
                selectinload(Organization.seller_roles), selectinload(Organization.buyer_roles)
            )
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def search_by_name(self, term: str, limit: int = 10) -> list[Organization]:
        """Case-insensitive, typo-tolerant name match directly against
        `organizations` — same pg_trgm pattern as
        `SellerRepository.search_by_organization_name`, but no join, since
        `/add-*`'s search-before-create step is about the organization
        itself, not an existing role on it. Reuses the same
        `ix_organizations_name_trgm` GIN index.

        Eager-loads `seller_roles`/`buyer_roles` — the org-selection-or-create
        modal needs to know, for each match, whether it already has the role
        kind being added, without a lazy-load per candidate.
        """
        similarity = func.similarity(Organization.name, term)
        stmt = (
            select(Organization)
            .where(
                or_(
                    Organization.name.ilike(f"%{term}%"),
                    similarity > _TRIGRAM_SIMILARITY_THRESHOLD,
                )
            )
            .options(
                selectinload(Organization.seller_roles), selectinload(Organization.buyer_roles)
            )
            .order_by(similarity.desc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def create(self, attio_id: str, name: str, **fields) -> Organization:
        """`attio_id` is always Attio's own `record_id` from a create that
        already succeeded there — this method never invents one.

        Upserts (`ON CONFLICT ... DO NOTHING`) rather than a plain insert:
        with the Attio webhook live, `record.created` for this same
        `attio_id` can reach `attio_sync.upsert.sync_organization` and land
        first, since that path is a single re-fetch-and-upsert while this
        one still has a role entry left to create in Attio first. On that
        race, the webhook's row — fetched straight from Attio, so at least
        as complete as this call's operator-entered subset — wins untouched
        rather than this raising `UniqueViolationError`.
        """
        stmt = (
            pg_insert(Organization)
            .values(attio_id=attio_id, name=name, **fields)
            .on_conflict_do_nothing(index_elements=["attio_id"])
        )
        await self._session.execute(stmt)
        await self._session.flush()
        org = await self.get_by_id(attio_id)
        assert org is not None
        return org

    async def update(self, attio_id: str, **fields) -> Organization | None:
        org = await self.get_by_id(attio_id)
        if org is None:
            return None
        for key, value in fields.items():
            setattr(org, key, value)
        await self._session.flush()
        return org
