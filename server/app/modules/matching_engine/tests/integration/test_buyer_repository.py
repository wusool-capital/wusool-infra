import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BuyerRole, Organization
from app.modules.matching_engine.persistence.repositories.buyers_repository import BuyerRepository


async def test_get_requirement_profile_returns_role_row(
    db_session: AsyncSession, any_buyer_role: BuyerRole
) -> None:
    repo = BuyerRepository(db_session)
    profile = await repo.get_requirement_profile(str(any_buyer_role.id))
    assert profile is not None
    assert profile.buyer_role_id == str(any_buyer_role.id)


async def test_search_by_organization_name_excludes_removed_org(
    db_session: AsyncSession,
) -> None:
    org = Organization(
        attio_id=f"test-org-{uuid.uuid4()}",
        name="Removed Buyer Match Org",
        removed_at=datetime.now(UTC),
    )
    db_session.add(org)
    await db_session.flush()

    role = BuyerRole(org_attio_id=org.attio_id, is_active=True)
    db_session.add(role)
    await db_session.flush()

    repo = BuyerRepository(db_session)
    results = await repo.search_by_organization_name("Removed Buyer Match Org")
    assert not any(r.buyer_role_id == str(role.id) for r in results)


async def test_search_by_organization_name_excludes_inactive_role(
    db_session: AsyncSession,
) -> None:
    org = Organization(attio_id=f"test-org-{uuid.uuid4()}", name="Stale Duplicate Buyer Match Org")
    db_session.add(org)
    await db_session.flush()

    role = BuyerRole(org_attio_id=org.attio_id, is_active=False)
    db_session.add(role)
    await db_session.flush()

    repo = BuyerRepository(db_session)
    results = await repo.search_by_organization_name("Stale Duplicate Buyer Match Org")
    assert not any(r.buyer_role_id == str(role.id) for r in results)
