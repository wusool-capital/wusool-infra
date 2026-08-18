"""Session-managed entry points for seller resolution and writes, so Slack
handlers never construct a repository/session themselves.
"""

from wusool_db.models import SellerRole

from ddl_commands.modules.sellers.application.resolution_service import (
    SellerResolution,
    SellerResolutionService,
)
from ddl_commands.modules.sellers.application.use_cases import (
    CreateSellerUseCase,
    UpdateSellerUseCase,
)
from ddl_commands.modules.sellers.infrastructure.repositories import SellerRepository
from ddl_commands.shared.database import get_sessionmaker


async def resolve_seller(seller_name: str) -> SellerResolution:
    async with get_sessionmaker()() as session:
        return await SellerResolutionService(SellerRepository(session)).resolve(seller_name)


async def resolve_seller_by_id(seller_role_id: str) -> SellerRole | None:
    async with get_sessionmaker()() as session:
        return await SellerResolutionService(SellerRepository(session)).resolve_by_id(
            seller_role_id
        )


def build_update_seller_use_case() -> UpdateSellerUseCase:
    return UpdateSellerUseCase(get_sessionmaker())


def build_create_seller_use_case() -> CreateSellerUseCase:
    return CreateSellerUseCase(get_sessionmaker())
