from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.buyers.infrastructure.models import BuyerRole


async def test_retrieve_buyer_role(any_buyer_role: BuyerRole) -> None:
    assert any_buyer_role.id
    assert any_buyer_role.org_attio_id


async def test_buyer_organization_relationship(
    db_session: AsyncSession, any_buyer_role: BuyerRole
) -> None:
    stmt = (
        select(BuyerRole)
        .where(BuyerRole.id == any_buyer_role.id)
        .options(selectinload(BuyerRole.organization))
    )
    role = (await db_session.execute(stmt)).scalar_one()
    assert role.organization is not None
    assert role.organization.name
