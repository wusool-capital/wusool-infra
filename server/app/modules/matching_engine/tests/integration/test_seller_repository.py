import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Organization, SellerRole
from app.modules.matching_engine.persistence.repositories.sellers_repository import SellerRepository


async def test_get_structured_fields_returns_role_row(
    db_session: AsyncSession, any_seller_role: SellerRole
) -> None:
    repo = SellerRepository(db_session)
    fields = await repo.get_structured_fields(str(any_seller_role.id))
    assert fields is not None
    assert fields.seller_role_id == str(any_seller_role.id)


async def test_get_eligible_sellers_excludes_inactive_and_removed(
    db_session: AsyncSession,
) -> None:
    org = Organization(attio_id=f"test-org-{uuid.uuid4()}", name="Eligible Sellers Test Org")
    removed_org = Organization(
        attio_id=f"test-org-{uuid.uuid4()}",
        name="Removed Org",
        removed_at=datetime.now(UTC),
    )
    db_session.add_all([org, removed_org])
    await db_session.flush()

    eligible = SellerRole(org_attio_id=org.attio_id, is_active=True)
    inactive = SellerRole(org_attio_id=org.attio_id, is_active=False)
    removed_role = SellerRole(
        org_attio_id=org.attio_id, is_active=True, removed_at=datetime.now(UTC)
    )
    role_on_removed_org = SellerRole(org_attio_id=removed_org.attio_id, is_active=True)
    db_session.add_all([eligible, inactive, removed_role, role_on_removed_org])
    await db_session.flush()

    repo = SellerRepository(db_session)
    results = await repo.get_eligible_sellers(limit=1000)
    result_ids = {r.seller_role_id for r in results}

    assert str(eligible.id) in result_ids
    assert str(inactive.id) not in result_ids
    assert str(removed_role.id) not in result_ids
    assert str(role_on_removed_org.id) not in result_ids
