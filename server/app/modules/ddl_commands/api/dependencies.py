"""Composition roots for Slack handlers — glue code: constructs
sessions/repositories/services and calls application-layer commands. No data
definitions here; those live in each concept's own `api/<concept>.py`.
"""

from app.models import BuyerRole, Organization, SellerRole
from app.modules.ddl_commands.api.buyers import BuyerResolutionRead, BuyerSummary
from app.modules.ddl_commands.api.sellers import SellerResolutionRead, SellerSummary
from app.modules.ddl_commands.application.ports.unit_of_work import DdlCommandsUnitOfWorkFactory
from app.modules.ddl_commands.application.service import DdlCommandsService
from app.modules.ddl_commands.bootstrap import (
    build_ddl_commands_service,
    build_ddl_commands_unit_of_work_factory,
    build_organization_repository,
)
from app.modules.ddl_commands.persistence.database import get_sessionmaker


def _ddl_commands_unit_of_work_factory() -> DdlCommandsUnitOfWorkFactory:
    return build_ddl_commands_unit_of_work_factory(get_sessionmaker())


def ddl_commands_service() -> DdlCommandsService:
    return build_ddl_commands_service(_ddl_commands_unit_of_work_factory())


async def resolve_buyer(buyer_name: str) -> BuyerResolutionRead:
    resolution = await ddl_commands_service().resolve_buyer(buyer_name)
    candidates = (
        [BuyerSummary.model_validate(role) for role in resolution.candidates]
        if resolution.candidates is not None
        else None
    )
    return BuyerResolutionRead(status=resolution.status, candidates=candidates)


async def resolve_buyer_by_id(buyer_role_id: str) -> BuyerRole | None:
    return await ddl_commands_service().resolve_buyer_by_id(buyer_role_id)


async def resolve_seller(seller_name: str) -> SellerResolutionRead:
    resolution = await ddl_commands_service().resolve_seller(seller_name)
    candidates = (
        [SellerSummary.model_validate(role) for role in resolution.candidates]
        if resolution.candidates is not None
        else None
    )
    return SellerResolutionRead(status=resolution.status, candidates=candidates)


async def resolve_seller_by_id(seller_role_id: str) -> SellerRole | None:
    return await ddl_commands_service().resolve_seller_by_id(seller_role_id)


async def search_organizations(term: str) -> list[Organization]:
    async with get_sessionmaker()() as session:
        return await build_organization_repository(session).search_by_name(term)


async def resolve_organization(attio_id: str) -> Organization | None:
    async with get_sessionmaker()() as session:
        return await build_organization_repository(session).get_by_id_with_roles(attio_id)
