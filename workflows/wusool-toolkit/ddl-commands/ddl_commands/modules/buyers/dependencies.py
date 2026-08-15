"""Session-managed entry points for buyer resolution and writes, so Slack
handlers never construct a repository/session themselves.
"""

from ddl_commands.modules.buyers.application.resolution_service import (
    BuyerResolution,
    BuyerResolutionService,
)
from ddl_commands.modules.buyers.application.use_cases import RemoveBuyerUseCase, UpdateBuyerUseCase
from ddl_commands.modules.buyers.infrastructure.models import BuyerRole
from ddl_commands.modules.buyers.infrastructure.repositories import BuyerRepository
from ddl_commands.shared.database import get_sessionmaker


async def resolve_buyer(buyer_name: str, *, include_removed: bool = False) -> BuyerResolution:
    async with get_sessionmaker()() as session:
        return await BuyerResolutionService(BuyerRepository(session)).resolve(
            buyer_name, include_removed=include_removed
        )


async def resolve_buyer_by_id(buyer_role_id: str) -> BuyerRole | None:
    async with get_sessionmaker()() as session:
        return await BuyerResolutionService(BuyerRepository(session)).resolve_by_id(
            buyer_role_id
        )


def build_update_buyer_use_case() -> UpdateBuyerUseCase:
    return UpdateBuyerUseCase(get_sessionmaker())


def build_remove_buyer_use_case() -> RemoveBuyerUseCase:
    return RemoveBuyerUseCase(get_sessionmaker())
