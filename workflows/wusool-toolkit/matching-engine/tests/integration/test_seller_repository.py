from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.sellers.infrastructure.repositories import SellerRepository
from wusool_db.models import SellerRole


async def test_get_structured_fields_returns_role_row(
    db_session: AsyncSession, any_seller_role: SellerRole
) -> None:
    repo = SellerRepository(db_session)
    fields = await repo.get_structured_fields(str(any_seller_role.id))
    assert fields is not None
    assert fields.id == any_seller_role.id
