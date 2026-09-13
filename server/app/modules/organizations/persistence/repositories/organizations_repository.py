"""Organization persistence — read/write, shared by `/edit-seller`/
`/edit-buyer` (an edit can touch org-level fields alongside role fields) and
`/add-seller`/`/add-buyer` (`search_by_name` powers the search-before-create
step, `create` is only ever called after the org's real Attio record already
exists — see `ddl_commands/README.md`, "Why Attio-first"). `add()`/`flush()`/
`execute()` only — never `commit()`/`rollback()`; the caller owns the
transaction boundary.
"""

from typing import Unpack

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Organization
from app.modules.organizations.application.ports.organizations import OrganizationFields

_TRIGRAM_SIMILARITY_THRESHOLD = 0.3


def org_name_trigram_predicate(term: str) -> tuple[ColumnElement[bool], ColumnElement[float]]:
    """Case-insensitive, typo-tolerant name-match predicate + similarity
    column to order by — the one canonical implementation, reused by every
    module that searches organizations by name (this repository's own
    `search_by_name`, `ddl_commands`' seller/buyer role search,
    `matching_engine`'s buyer search). `pg_trgm` (001_extensions.sql, GIN
    index in 007_org_name_trgm_index.sql) ranks by trigram similarity, so a
    misspelled name still surfaces a match — but the plain `ILIKE`
    substring match is always included too (`OR`), so an exact/partial
    typed name never regresses to relying on a similarity score.

    The threshold is an explicit constant, not `pg_trgm`'s own `%`
    similarity operator: that operator depends on a session-level GUC
    (`pg_trgm.similarity_threshold`), while comparing `func.similarity(...)`
    against a literal is equivalent to that operator's own default and
    doesn't depend on session state.

    Kept here, not in a `domain/` module: `organizations` has none (it's a
    full-access peer, see this module's own `__init__.py` docstring), and
    the predicate is a SQLAlchemy construct, not framework-free logic.
    """
    similarity = func.similarity(Organization.name, term)
    return (
        or_(Organization.name.ilike(f"%{term}%"), similarity > _TRIGRAM_SIMILARITY_THRESHOLD),
        similarity,
    )


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
        """`org_name_trigram_predicate` directly against `organizations` —
        no join, since `/add-*`'s search-before-create step is about the
        organization itself, not an existing role on it. Reuses the same
        `ix_organizations_name_trgm` GIN index.

        Eager-loads `seller_roles`/`buyer_roles` — the org-selection-or-create
        modal needs to know, for each match, whether it already has the role
        kind being added, without a lazy-load per candidate.
        """
        predicate, similarity = org_name_trigram_predicate(term)
        stmt = (
            select(Organization)
            .where(predicate)
            .options(
                selectinload(Organization.seller_roles), selectinload(Organization.buyer_roles)
            )
            .order_by(similarity.desc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def create(
        self, attio_id: str, name: str, **fields: Unpack[OrganizationFields]
    ) -> Organization:
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

    async def lock(self, attio_id: str) -> None:
        """Row-locks the organization for the rest of the caller's
        transaction, serializing concurrent `/add-buyer`/`/add-seller`
        submissions for the same org.

        Since the 2026-08-28 migration (`b8f4c1e93a56`) `org_attio_id` is no
        longer unique on the role tables, so "this org already has an active
        role" is an application-level check with a TOCTOU window rather than
        something the DB rejects outright. Holding this lock across that
        check and the insert that follows is what closes it — see
        `CreateBuyerUseCase.execute`.

        A missing org is a no-op (no row to lock): the role insert's FK to
        `organizations.attio_id` is still the error path for that, unchanged.
        """
        await self._session.execute(
            select(Organization.attio_id).where(Organization.attio_id == attio_id).with_for_update()
        )

    async def update(
        self, attio_id: str, **fields: Unpack[OrganizationFields]
    ) -> Organization | None:
        org = await self.get_by_id(attio_id)
        if org is None:
            return None
        for key, value in fields.items():
            setattr(org, key, value)
        await self._session.flush()
        return org
