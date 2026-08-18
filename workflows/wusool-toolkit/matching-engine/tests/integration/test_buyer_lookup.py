from sqlalchemy.ext.asyncio import AsyncSession
from wusool_db.models import BuyerRole

from app.modules.buyers.infrastructure.repositories import BuyerRepository


async def test_search_by_organization_name_case_insensitive_partial(
    db_session: AsyncSession, any_buyer_role: BuyerRole
) -> None:
    repo = BuyerRepository(db_session)
    await db_session.refresh(any_buyer_role, attribute_names=["organization"])
    org_name = any_buyer_role.organization.name
    term = org_name[: max(3, len(org_name) // 2)]

    results = await repo.search_by_organization_name(term.upper())

    assert any(role.id == any_buyer_role.id for role in results)
