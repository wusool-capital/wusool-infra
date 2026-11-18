"""A role Attio deleted is skipped everywhere: its delete event sets `removed_at` and
leaves `is_active` true until the nightly resync."""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BuyerRole, Organization, SellerRole
from app.modules.ddl_commands.persistence.repositories.buyers_repository import BuyerRepository
from app.modules.ddl_commands.persistence.repositories.sellers_repository import (
    SellerRepository,
)


async def test_a_buyer_role_attio_deleted_is_not_found_by_id_and_does_not_count_as_existing(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    vertical = f"Test vertical {uuid.uuid4()}"
    live = BuyerRole(org_attio_id=throwaway_org.attio_id, target_vertical=vertical, is_active=True)
    gone = BuyerRole(
        org_attio_id=throwaway_org.attio_id,
        target_vertical=f"{vertical} gone",
        is_active=True,
        removed_at=datetime.now(UTC),
    )
    db_session.add_all([live, gone])
    await db_session.flush()
    repo = BuyerRepository(db_session)

    assert await repo.get_with_organization(str(live.id)) is not None
    assert await repo.get_with_organization(str(gone.id)) is None
    assert [r.id for r in await repo.get_many_with_organization([str(live.id), str(gone.id)])] == [
        live.id
    ]
    assert await repo.get_active_by_org_and_vertical(throwaway_org.attio_id, vertical) is not None
    assert (
        await repo.get_active_by_org_and_vertical(throwaway_org.attio_id, f"{vertical} gone")
        is None
    )  # so an add for that vertical is not refused as "existing"


async def test_a_seller_role_attio_deleted_is_not_found_by_id_and_does_not_count_as_existing(
    db_session: AsyncSession,
) -> None:
    org = Organization(attio_id=f"test-org-{uuid.uuid4()}", name="Seller Removed Co")
    db_session.add(org)
    await db_session.flush()
    gone = SellerRole(org_attio_id=org.attio_id, is_active=True, removed_at=datetime.now(UTC))
    db_session.add(gone)
    await db_session.flush()
    repo = SellerRepository(db_session)

    assert await repo.get_with_organization(str(gone.id)) is None
    assert await repo.get_many_with_organization([str(gone.id)]) == []
    assert await repo.get_by_org_attio_id(org.attio_id) is None
    live = SellerRole(org_attio_id=org.attio_id, is_active=True)
    db_session.add(live)
    await db_session.flush()
    found = await repo.get_by_org_attio_id(org.attio_id)
    assert found is not None and found.id == live.id
