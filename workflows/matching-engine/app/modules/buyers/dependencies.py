"""Session-managed entry points for buyer resolution, so Slack handlers
never construct a repository/session themselves (§2, §36).
"""

from app.modules.buyers.application.resolution_service import (
    BuyerResolution,
    BuyerResolutionService,
)
from app.modules.buyers.domain.value_objects import BuyerContext
from app.modules.buyers.infrastructure.repositories import BuyerRepository
from app.shared.database import get_sessionmaker


async def resolve_buyer(buyer_name: str) -> BuyerResolution:
    async with get_sessionmaker()() as session:
        return await BuyerResolutionService(BuyerRepository(session)).resolve(buyer_name)


async def resolve_buyer_by_id(buyer_role_id: str) -> BuyerContext | None:
    async with get_sessionmaker()() as session:
        return await BuyerResolutionService(BuyerRepository(session)).resolve_by_id(buyer_role_id)
