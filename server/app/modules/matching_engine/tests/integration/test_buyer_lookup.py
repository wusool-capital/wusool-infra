import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BuyerRole, Organization
from app.modules.matching_engine.persistence.repositories.buyers_repository import BuyerRepository


async def test_search_by_organization_name_case_insensitive_partial(
    db_session: AsyncSession, any_buyer_role: BuyerRole
) -> None:
    repo = BuyerRepository(db_session)
    await db_session.refresh(any_buyer_role, attribute_names=["organization"])
    org_name = any_buyer_role.organization.name
    term = org_name[: max(3, len(org_name) // 2)]

    results = await repo.search_by_organization_name(term.upper())

    assert any(role.buyer_role_id == str(any_buyer_role.id) for role in results)


async def test_search_by_organization_name_excludes_inactive_role(
    db_session: AsyncSession,
) -> None:
    """Regression: this method used to omit the `is_active` filter
    `ddl_commands.BuyerRepository`'s own version of this same query has —
    an org can hold stale/duplicate rows post-migration, and `/find-match`
    must never resolve one as if it were the real, current buyer role.
    """
    org = Organization(attio_id=f"test-{uuid.uuid4()}", name="Stale Duplicate Buyer Co")
    db_session.add(org)
    await db_session.flush()
    role = BuyerRole(org_attio_id=org.attio_id, is_active=False)
    db_session.add(role)
    await db_session.flush()

    repo = BuyerRepository(db_session)
    results = await repo.search_by_organization_name("Stale Duplicate Buyer Co")

    assert not any(r.org_attio_id == org.attio_id for r in results)
