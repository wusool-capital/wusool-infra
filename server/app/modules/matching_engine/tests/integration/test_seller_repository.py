from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SellerRole
from app.modules.matching_engine.persistence.repositories.sellers_repository import SellerRepository


async def test_get_structured_fields_returns_role_row(
    db_session: AsyncSession, any_seller_role: SellerRole
) -> None:
    repo = SellerRepository(db_session)
    fields = await repo.get_structured_fields(str(any_seller_role.id))
    assert fields is not None
    assert fields.seller_role_id == str(any_seller_role.id)
