from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import SellerRole


async def test_retrieve_seller_role(any_seller_role: SellerRole) -> None:
    assert any_seller_role.id
    assert any_seller_role.org_attio_id


async def test_seller_organization_relationship(
    db_session: AsyncSession, any_seller_role: SellerRole
) -> None:
    stmt = (
        select(SellerRole)
        .where(SellerRole.id == any_seller_role.id)
        .options(selectinload(SellerRole.organization))
    )
    role = (await db_session.execute(stmt)).scalar_one()
    assert role.organization is not None
    assert role.organization.name
