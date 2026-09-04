import asyncio
import uuid

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Organization, SellerRole
from app.modules.ddl_commands.application.ports.unit_of_work import DdlCommandsUnitOfWorkFactory
from app.modules.ddl_commands.application.sellers import (
    CreateSellerUseCase,
    SellerAlreadyExistsError,
    SellerNotFoundError,
    UpdateSellerUseCase,
)
from app.modules.ddl_commands.persistence.database import get_sessionmaker
from app.modules.ddl_commands.persistence.unit_of_work import SqlAlchemyDdlCommandsUnitOfWork
from app.modules.organizations import OrganizationRepository


def _uow_factory(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> DdlCommandsUnitOfWorkFactory:
    return lambda: SqlAlchemyDdlCommandsUnitOfWork(db_sessionmaker)


async def _seed_seller(db_sessionmaker: async_sessionmaker[AsyncSession]) -> str:
    async with db_sessionmaker() as session:
        org = Organization(attio_id=f"test-org-{uuid.uuid4()}", name="Use Case Test Co")
        session.add(org)
        await session.flush()
        role = SellerRole(org_attio_id=org.attio_id, outreach_tier="cold")
        session.add(role)
        await session.flush()
        role_id = str(role.id)
        await session.commit()
    return role_id


async def test_update_not_found_raises(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    use_case = UpdateSellerUseCase(_uow_factory(db_sessionmaker))
    with pytest.raises(SellerNotFoundError):
        await use_case.execute(str(uuid.uuid4()), {"outreach_tier": "warm"})


async def test_update_applies_fields(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    seller_id = await _seed_seller(db_sessionmaker)

    updated = await UpdateSellerUseCase(_uow_factory(db_sessionmaker)).execute(
        seller_id, {"outreach_tier": "warm"}
    )

    assert updated.outreach_tier == "warm"


async def test_create_with_new_org_inserts_org_and_role(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    attio_id = f"test-org-{uuid.uuid4()}"

    role = await CreateSellerUseCase(_uow_factory(db_sessionmaker)).execute(
        org_attio_id=attio_id,
        entry_id="entry-1",
        is_new_org=True,
        org_name="Brand New Seller Co",
        org_fields={"hq_country": "AE"},
        role_fields={"outreach_tier": "Tier 1"},
    )

    assert role.org_attio_id == attio_id
    assert role.outreach_tier == "Tier 1"
    assert role.is_active is True
    assert role.legacy_entry_id == "entry-1"

    async with db_sessionmaker() as session:
        org = await OrganizationRepository(session).get_by_id(attio_id)
        assert org is not None
        assert org.name == "Brand New Seller Co"
        assert org.hq_country == "AE"
        assert org.is_active is True


async def test_create_attaches_to_existing_org(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    async with db_sessionmaker() as session:
        org = Organization(attio_id=f"test-org-{uuid.uuid4()}", name="Existing Co")
        session.add(org)
        await session.flush()
        await session.commit()
        attio_id = org.attio_id

    role = await CreateSellerUseCase(_uow_factory(db_sessionmaker)).execute(
        org_attio_id=attio_id,
        entry_id="entry-2",
        is_new_org=False,
        org_fields=None,
        role_fields={"outreach_tier": "Tier 2"},
    )

    assert role.org_attio_id == attio_id
    assert role.outreach_tier == "Tier 2"
    assert role.is_active is True
    assert role.legacy_entry_id == "entry-2"


async def test_create_raises_when_role_already_exists(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    async with db_sessionmaker() as session:
        org = Organization(attio_id=f"test-org-{uuid.uuid4()}", name="Already Has Seller Co")
        session.add(org)
        await session.flush()
        role = SellerRole(org_attio_id=org.attio_id, is_active=True)
        session.add(role)
        await session.flush()
        await session.commit()
        attio_id = org.attio_id

    with pytest.raises(SellerAlreadyExistsError):
        await CreateSellerUseCase(_uow_factory(db_sessionmaker)).execute(
            org_attio_id=attio_id,
            entry_id="entry-3",
            is_new_org=False,
            org_fields=None,
            role_fields={"outreach_tier": "Tier 1"},
        )


async def test_create_succeeds_when_existing_role_is_inactive(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """A stale/inactive duplicate role (a reconciliation artifact from the
    2026-08-28 migration allowing multiple rows per org) must not block a
    new `/add-seller` for the same organization.
    """
    async with db_sessionmaker() as session:
        org = Organization(attio_id=f"test-org-{uuid.uuid4()}", name="Stale Dup Seller Co")
        session.add(org)
        await session.flush()
        role = SellerRole(org_attio_id=org.attio_id, is_active=False)
        session.add(role)
        await session.flush()
        await session.commit()
        attio_id = org.attio_id

    role = await CreateSellerUseCase(_uow_factory(db_sessionmaker)).execute(
        org_attio_id=attio_id,
        entry_id="entry-5",
        is_new_org=False,
        org_fields=None,
        role_fields={"outreach_tier": "Tier 1"},
    )

    assert role.is_active is True
    assert role.legacy_entry_id == "entry-5"


async def test_create_does_not_raise_when_webhook_already_wrote_this_same_entry(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """With the Attio webhook live, `sync_seller_role` for the entry this
    call is about to write can land first and insert the exact same row —
    that's not a genuine conflict, just this call's own write arriving via
    a second path, told apart by a matching `legacy_entry_id`.
    """
    async with db_sessionmaker() as session:
        org = Organization(attio_id=f"test-org-{uuid.uuid4()}", name="Webhook-Raced Seller Co")
        session.add(org)
        await session.flush()
        role = SellerRole(org_attio_id=org.attio_id, legacy_entry_id="entry-4", is_active=True)
        session.add(role)
        await session.flush()
        await session.commit()
        attio_id = org.attio_id

    role = await CreateSellerUseCase(_uow_factory(db_sessionmaker)).execute(
        org_attio_id=attio_id,
        entry_id="entry-4",
        is_new_org=False,
        org_fields=None,
        role_fields={"outreach_tier": "Tier 1"},
    )

    assert role.org_attio_id == attio_id
    assert role.legacy_entry_id == "entry-4"


async def test_concurrent_create_yields_one_active_role() -> None:
    """Two `/add-seller` submissions for the same org, landing inside the
    same window with *different* Attio entries: exactly one must win.

    Deliberately does not use the `db_sessionmaker` fixture — that binds
    every session to one connection via savepoints, so two gathered calls
    serialize on that connection and `FOR UPDATE` never blocks, which would
    make this pass with or without `OrganizationRepository.lock`. This needs
    two real connections and real commits, hence the manual cleanup.
    """
    sessionmaker = get_sessionmaker()
    attio_id = f"test-org-{uuid.uuid4()}"
    try:
        async with sessionmaker() as session:
            session.add(Organization(attio_id=attio_id, name="Concurrent Seller Co"))
            await session.commit()
    except Exception as exc:  # no SSM tunnel open
        pytest.skip(f"database not reachable: {exc}")

    async def _create(entry_id: str) -> SellerRole:
        return await CreateSellerUseCase(_uow_factory(sessionmaker)).execute(
            org_attio_id=attio_id,
            entry_id=entry_id,
            is_new_org=False,
            org_fields=None,
            role_fields={"outreach_tier": "Tier 1"},
        )

    try:
        results = await asyncio.gather(
            _create("entry-concurrent-a"),
            _create("entry-concurrent-b"),
            return_exceptions=True,
        )

        winners = [r for r in results if isinstance(r, SellerRole)]
        losers = [r for r in results if isinstance(r, SellerAlreadyExistsError)]
        assert len(winners) == 1, results
        assert len(losers) == 1, results

        async with sessionmaker() as session:
            active = await session.scalar(
                select(func.count())
                .select_from(SellerRole)
                .where(SellerRole.org_attio_id == attio_id, SellerRole.is_active.is_(True))
            )
        assert active == 1
    finally:
        async with sessionmaker() as session:
            await session.execute(delete(SellerRole).where(SellerRole.org_attio_id == attio_id))
            await session.execute(delete(Organization).where(Organization.attio_id == attio_id))
            await session.commit()
