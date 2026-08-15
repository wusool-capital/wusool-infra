import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.sellers.application.use_cases import (
    ArchiveSellerUseCase,
    SellerAlreadyArchivedError,
    SellerNotFoundError,
    UpdateSellerUseCase,
)
from app.modules.sellers.infrastructure.models import SellerRole
from app.shared.database.models import Organization


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


async def test_archive_twice_raises_already_archived(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    seller_id = await _seed_seller(db_sessionmaker)
    use_case = ArchiveSellerUseCase(db_sessionmaker)

    await use_case.execute(seller_id, "U1")
    with pytest.raises(SellerAlreadyArchivedError):
        await use_case.execute(seller_id, "U1")


async def test_update_not_found_raises(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    use_case = UpdateSellerUseCase(db_sessionmaker)
    with pytest.raises(SellerNotFoundError):
        await use_case.execute(str(uuid.uuid4()), {"outreach_tier": "warm"}, "U1")


async def test_update_archived_without_restore_raises(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    seller_id = await _seed_seller(db_sessionmaker)
    await ArchiveSellerUseCase(db_sessionmaker).execute(seller_id, "U1")

    with pytest.raises(SellerAlreadyArchivedError):
        await UpdateSellerUseCase(db_sessionmaker).execute(
            seller_id, {"outreach_tier": "warm"}, "U2"
        )


async def test_update_archived_with_restore_clears_archived_at_and_applies_fields(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    seller_id = await _seed_seller(db_sessionmaker)
    await ArchiveSellerUseCase(db_sessionmaker).execute(seller_id, "U1")

    updated = await UpdateSellerUseCase(db_sessionmaker).execute(
        seller_id, {"outreach_tier": "warm"}, "U2", restore=True
    )

    assert updated.archived_at is None
    assert updated.outreach_tier == "warm"
    assert updated.bot_managed_by == "U2"
