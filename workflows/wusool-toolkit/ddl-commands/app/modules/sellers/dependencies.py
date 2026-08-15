"""Session-managed entry points for seller resolution and writes, so Slack
handlers never construct a repository/session themselves.
"""

from app.modules.sellers.application.resolution_service import (
    SellerResolution,
    SellerResolutionService,
)
from app.modules.sellers.application.use_cases import ArchiveSellerUseCase, UpdateSellerUseCase
from app.modules.sellers.infrastructure.models import SellerRole
from app.modules.sellers.infrastructure.repositories import SellerRepository
from app.shared.database import get_sessionmaker


async def resolve_seller(seller_name: str, *, include_archived: bool = False) -> SellerResolution:
    async with get_sessionmaker()() as session:
        return await SellerResolutionService(SellerRepository(session)).resolve(
            seller_name, include_archived=include_archived
        )


async def resolve_seller_by_id(seller_role_id: str) -> SellerRole | None:
    async with get_sessionmaker()() as session:
        return await SellerResolutionService(SellerRepository(session)).resolve_by_id(
            seller_role_id
        )


def build_update_seller_use_case() -> UpdateSellerUseCase:
    return UpdateSellerUseCase(get_sessionmaker())


def build_archive_seller_use_case() -> ArchiveSellerUseCase:
    return ArchiveSellerUseCase(get_sessionmaker())
