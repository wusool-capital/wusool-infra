import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from wusool_db.models import BuyerRole, Organization

from ddl_commands.modules.buyers.application.use_cases import (
    BuyerAlreadyExistsError,
    BuyerNotFoundError,
    CreateBuyerUseCase,
    UpdateBuyerUseCase,
)
from ddl_commands.shared.database.organization_repository import OrganizationRepository


async def _seed_buyer(db_sessionmaker: async_sessionmaker[AsyncSession]) -> str:
    async with db_sessionmaker() as session:
        org = Organization(attio_id=f"test-org-{uuid.uuid4()}", name="Buyer Use Case Test Co")
        session.add(org)
        await session.flush()
        role = BuyerRole(org_attio_id=org.attio_id, model="Buy-and-build")
        session.add(role)
        await session.flush()
        role_id = str(role.id)
        await session.commit()
    return role_id


async def test_update_not_found_raises(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    use_case = UpdateBuyerUseCase(db_sessionmaker)
    with pytest.raises(BuyerNotFoundError):
        await use_case.execute(str(uuid.uuid4()), {"model": "Roll-up"})


async def test_update_applies_fields(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    buyer_id = await _seed_buyer(db_sessionmaker)

    updated = await UpdateBuyerUseCase(db_sessionmaker).execute(buyer_id, {"model": "Roll-up"})

    assert updated.model == "Roll-up"


async def test_create_with_new_org_inserts_org_and_role(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    attio_id = f"test-org-{uuid.uuid4()}"

    role = await CreateBuyerUseCase(db_sessionmaker).execute(
        org_attio_id=attio_id,
        entry_id="entry-1",
        is_new_org=True,
        org_name="Brand New Buyer Co",
        org_fields={"hq_country": "AE"},
        role_fields={"model": "Model 1 (Network)"},
    )

    assert role.org_attio_id == attio_id
    assert role.model == "Model 1 (Network)"
    assert role.is_active is True
    assert role.legacy_entry_id == "entry-1"

    async with db_sessionmaker() as session:
        org = await OrganizationRepository(session).get_by_id(attio_id)
        assert org is not None
        assert org.name == "Brand New Buyer Co"
        assert org.hq_country == "AE"
        assert org.is_active is True


async def test_create_attaches_to_existing_org(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    async with db_sessionmaker() as session:
        org = Organization(attio_id=f"test-org-{uuid.uuid4()}", name="Existing Buyer Co")
        session.add(org)
        await session.flush()
        await session.commit()
        attio_id = org.attio_id

    role = await CreateBuyerUseCase(db_sessionmaker).execute(
        org_attio_id=attio_id,
        entry_id="entry-2",
        is_new_org=False,
        org_fields=None,
        role_fields={"model": "Model 2 (Full Mandate)"},
    )

    assert role.org_attio_id == attio_id
    assert role.model == "Model 2 (Full Mandate)"
    assert role.is_active is True
    assert role.legacy_entry_id == "entry-2"


async def test_create_raises_when_role_already_exists(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    async with db_sessionmaker() as session:
        org = Organization(attio_id=f"test-org-{uuid.uuid4()}", name="Already Has Buyer Co")
        session.add(org)
        await session.flush()
        role = BuyerRole(org_attio_id=org.attio_id, is_active=True)
        session.add(role)
        await session.flush()
        await session.commit()
        attio_id = org.attio_id

    with pytest.raises(BuyerAlreadyExistsError):
        await CreateBuyerUseCase(db_sessionmaker).execute(
            org_attio_id=attio_id,
            entry_id="entry-3",
            is_new_org=False,
            org_fields=None,
            role_fields={"model": "Model 1 (Network)"},
        )


async def test_create_succeeds_when_existing_role_is_inactive(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """A stale/inactive duplicate role (a reconciliation artifact from the
    2026-08-28 migration allowing multiple rows per org) must not block a
    new `/add-buyer` for the same organization.
    """
    async with db_sessionmaker() as session:
        org = Organization(attio_id=f"test-org-{uuid.uuid4()}", name="Stale Dup Buyer Co")
        session.add(org)
        await session.flush()
        role = BuyerRole(org_attio_id=org.attio_id, is_active=False)
        session.add(role)
        await session.flush()
        await session.commit()
        attio_id = org.attio_id

    role = await CreateBuyerUseCase(db_sessionmaker).execute(
        org_attio_id=attio_id,
        entry_id="entry-5",
        is_new_org=False,
        org_fields=None,
        role_fields={"model": "Model 1 (Network)"},
    )

    assert role.is_active is True
    assert role.legacy_entry_id == "entry-5"


async def test_create_does_not_raise_when_webhook_already_wrote_this_same_entry(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """With the Attio webhook live, `sync_buyer_role` for the entry this
    call is about to write can land first and insert the exact same row —
    that's not a genuine conflict, just this call's own write arriving via
    a second path, told apart by a matching `legacy_entry_id`.
    """
    async with db_sessionmaker() as session:
        org = Organization(attio_id=f"test-org-{uuid.uuid4()}", name="Webhook-Raced Buyer Co")
        session.add(org)
        await session.flush()
        role = BuyerRole(org_attio_id=org.attio_id, legacy_entry_id="entry-4", is_active=True)
        session.add(role)
        await session.flush()
        await session.commit()
        attio_id = org.attio_id

    role = await CreateBuyerUseCase(db_sessionmaker).execute(
        org_attio_id=attio_id,
        entry_id="entry-4",
        is_new_org=False,
        org_fields=None,
        role_fields={"model": "Model 1 (Network)"},
    )

    assert role.org_attio_id == attio_id
    assert role.legacy_entry_id == "entry-4"
