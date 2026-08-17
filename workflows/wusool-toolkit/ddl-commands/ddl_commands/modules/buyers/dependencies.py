"""Session-managed entry points for buyer resolution and writes, so Slack
handlers never construct a repository/session themselves.
"""

from ddl_commands.modules.buyers.application.resolution_service import (
    BuyerResolution,
    BuyerResolutionService,
)
from ddl_commands.modules.buyers.application.use_cases import (
    CreateBuyerUseCase,
    UpdateBuyerUseCase,
)
from ddl_commands.modules.buyers.infrastructure.models import BuyerRole
from ddl_commands.modules.buyers.infrastructure.repositories import BuyerRepository
from ddl_commands.shared.database import get_sessionmaker


async def resolve_buyer(buyer_name: str) -> BuyerResolution:
    async with get_sessionmaker()() as session:
        return await BuyerResolutionService(BuyerRepository(session)).resolve(buyer_name)


async def resolve_buyer_by_id(buyer_role_id: str) -> BuyerRole | None:
    async with get_sessionmaker()() as session:
        return await BuyerResolutionService(BuyerRepository(session)).resolve_by_id(
            buyer_role_id
        )


def build_update_buyer_use_case() -> UpdateBuyerUseCase:
    return UpdateBuyerUseCase(get_sessionmaker())


def build_create_buyer_use_case() -> CreateBuyerUseCase:
    return CreateBuyerUseCase(get_sessionmaker())
