from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BuyerRole
from app.modules.matching_engine.persistence.repositories.buyers_repository import BuyerRepository


async def test_get_requirement_profile_returns_role_row(
    db_session: AsyncSession, any_buyer_role: BuyerRole
) -> None:
    repo = BuyerRepository(db_session)
    profile = await repo.get_requirement_profile(str(any_buyer_role.id))
    assert profile is not None
    assert profile.buyer_role_id == str(any_buyer_role.id)
