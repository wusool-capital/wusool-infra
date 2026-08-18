from sqlalchemy.ext.asyncio import AsyncSession
from wusool_db.models import BuyerRole

from app.modules.buyers.infrastructure.repositories import BuyerRepository


async def test_get_requirement_profile_returns_role_row(
    db_session: AsyncSession, any_buyer_role: BuyerRole
) -> None:
    repo = BuyerRepository(db_session)
    profile = await repo.get_requirement_profile(str(any_buyer_role.id))
    assert profile is not None
    assert profile.id == any_buyer_role.id
