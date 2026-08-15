"""Session-managed entry points for buyer resolution and writes, so Slack
handlers never construct a repository/session themselves.
"""

from app.modules.buyers.application.resolution_service import (
    BuyerResolution,
    BuyerResolutionService,
)
from app.modules.buyers.application.use_cases import ArchiveBuyerUseCase, UpdateBuyerUseCase
from app.modules.buyers.infrastructure.models import BuyerRole
from app.modules.buyers.infrastructure.repositories import BuyerRepository
from app.shared.database import get_sessionmaker


async def resolve_buyer(buyer_name: str, *, include_archived: bool = False) -> BuyerResolution:
    async with get_sessionmaker()() as session:
        return await BuyerResolutionService(BuyerRepository(session)).resolve(
            buyer_name, include_archived=include_archived
        )


async def resolve_buyer_by_id(buyer_role_id: str) -> BuyerRole | None:
    async with get_sessionmaker()() as session:
        return await BuyerResolutionService(BuyerRepository(session)).resolve_by_id(
            buyer_role_id
        )


def build_update_buyer_use_case() -> UpdateBuyerUseCase:
    return UpdateBuyerUseCase(get_sessionmaker())


def build_archive_buyer_use_case() -> ArchiveBuyerUseCase:
    return ArchiveBuyerUseCase(get_sessionmaker())
