import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.buyers.application.use_cases import (
    BuyerAlreadyRemovedError,
    BuyerNotFoundError,
    RemoveBuyerUseCase,
    UpdateBuyerUseCase,
)
from app.modules.buyers.infrastructure.models import BuyerRole
from app.shared.database.models import Organization


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


async def test_remove_twice_raises_already_removed(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    buyer_id = await _seed_buyer(db_sessionmaker)
    use_case = RemoveBuyerUseCase(db_sessionmaker)

    await use_case.execute(buyer_id, "U1")
    with pytest.raises(BuyerAlreadyRemovedError):
        await use_case.execute(buyer_id, "U1")


async def test_update_not_found_raises(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    use_case = UpdateBuyerUseCase(db_sessionmaker)
    with pytest.raises(BuyerNotFoundError):
        await use_case.execute(str(uuid.uuid4()), {"model": "Roll-up"}, "U1")


async def test_update_removed_without_restore_raises(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    buyer_id = await _seed_buyer(db_sessionmaker)
    await RemoveBuyerUseCase(db_sessionmaker).execute(buyer_id, "U1")

    with pytest.raises(BuyerAlreadyRemovedError):
        await UpdateBuyerUseCase(db_sessionmaker).execute(buyer_id, {"model": "Roll-up"}, "U2")


async def test_update_removed_with_restore_clears_removed_at_and_applies_fields(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    buyer_id = await _seed_buyer(db_sessionmaker)
    await RemoveBuyerUseCase(db_sessionmaker).execute(buyer_id, "U1")

    updated = await UpdateBuyerUseCase(db_sessionmaker).execute(
        buyer_id, {"model": "Roll-up"}, "U2", restore=True
    )

    assert updated.removed_at is None
    assert updated.model == "Roll-up"
    assert updated.bot_managed_by == "U2"
