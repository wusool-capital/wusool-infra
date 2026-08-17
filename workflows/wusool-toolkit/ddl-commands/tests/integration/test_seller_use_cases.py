import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ddl_commands.modules.sellers.application.use_cases import (
    CreateSellerUseCase,
    SellerAlreadyExistsError,
    SellerNotFoundError,
    UpdateSellerUseCase,
)
from ddl_commands.shared.database.organization_repository import OrganizationRepository
from wusool_db.models import Organization, SellerRole


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
    use_case = UpdateSellerUseCase(db_sessionmaker)
    with pytest.raises(SellerNotFoundError):
        await use_case.execute(str(uuid.uuid4()), {"outreach_tier": "warm"})


async def test_update_applies_fields(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    seller_id = await _seed_seller(db_sessionmaker)

    updated = await UpdateSellerUseCase(db_sessionmaker).execute(
        seller_id, {"outreach_tier": "warm"}
    )

    assert updated.outreach_tier == "warm"


async def test_create_with_new_org_inserts_org_and_role(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    attio_id = f"test-org-{uuid.uuid4()}"

    role = await CreateSellerUseCase(db_sessionmaker).execute(
        org_attio_id=attio_id,
        is_new_org=True,
        org_name="Brand New Seller Co",
        org_fields={"hq_country": "AE"},
        role_fields={"outreach_tier": "Tier 1"},
    )

    assert role.org_attio_id == attio_id
    assert role.outreach_tier == "Tier 1"

    async with db_sessionmaker() as session:
        org = await OrganizationRepository(session).get_by_id(attio_id)
        assert org is not None
        assert org.name == "Brand New Seller Co"
        assert org.hq_country == "AE"


async def test_create_attaches_to_existing_org(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    async with db_sessionmaker() as session:
        org = Organization(attio_id=f"test-org-{uuid.uuid4()}", name="Existing Co")
        session.add(org)
        await session.flush()
        await session.commit()
        attio_id = org.attio_id

    role = await CreateSellerUseCase(db_sessionmaker).execute(
        org_attio_id=attio_id,
        is_new_org=False,
        org_fields=None,
        role_fields={"outreach_tier": "Tier 2"},
    )

    assert role.org_attio_id == attio_id
    assert role.outreach_tier == "Tier 2"


async def test_create_raises_when_role_already_exists(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    async with db_sessionmaker() as session:
        org = Organization(attio_id=f"test-org-{uuid.uuid4()}", name="Already Has Seller Co")
        session.add(org)
        await session.flush()
        role = SellerRole(org_attio_id=org.attio_id)
        session.add(role)
        await session.flush()
        await session.commit()
        attio_id = org.attio_id

    with pytest.raises(SellerAlreadyExistsError):
        await CreateSellerUseCase(db_sessionmaker).execute(
            org_attio_id=attio_id,
            is_new_org=False,
            org_fields=None,
            role_fields={"outreach_tier": "Tier 1"},
        )
