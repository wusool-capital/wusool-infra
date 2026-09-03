"""Composition roots for Slack handlers — glue code: constructs
sessions/repositories/services and calls application-layer commands. No data
definitions here; those live in each concept's own `api/<concept>.py`.
"""

from dataclasses import dataclass

from app.models import BuyerRole, Organization, SellerRole
from app.modules.ddl_commands.api.buyers import BuyerSummary
from app.modules.ddl_commands.api.sellers import SellerSummary
from app.modules.ddl_commands.application.buyers import (
    BuyerResolutionService,
    CreateBuyerUseCase,
    ResolutionStatus,
    UpdateBuyerUseCase,
)
from app.modules.ddl_commands.application.sellers import (
    CreateSellerUseCase,
    SellerResolutionService,
    UpdateSellerUseCase,
)
from app.modules.ddl_commands.bootstrap import (
    build_buyer_repository,
    build_ddl_commands_unit_of_work_factory,
    build_organization_repository,
    build_seller_repository,
)
from app.modules.ddl_commands.persistence.database import get_sessionmaker


def _ddl_commands_unit_of_work_factory():
    return build_ddl_commands_unit_of_work_factory(get_sessionmaker())


@dataclass(frozen=True)
class BuyerResolutionRead:
    status: ResolutionStatus
    candidates: list[BuyerSummary] | None = None


async def resolve_buyer(buyer_name: str) -> BuyerResolutionRead:
    async with get_sessionmaker()() as session:
        resolution = await BuyerResolutionService(
            build_buyer_repository(session)
        ).resolve(buyer_name)
        candidates = (
            [BuyerSummary.model_validate(role) for role in resolution.candidates]
            if resolution.candidates is not None
            else None
        )
        return BuyerResolutionRead(status=resolution.status, candidates=candidates)


async def resolve_buyer_by_id(buyer_role_id: str) -> BuyerRole | None:
    async with get_sessionmaker()() as session:
        return await BuyerResolutionService(build_buyer_repository(session)).resolve_by_id(
            buyer_role_id
        )


def build_update_buyer_use_case() -> UpdateBuyerUseCase:
    return UpdateBuyerUseCase(_ddl_commands_unit_of_work_factory())


def build_create_buyer_use_case() -> CreateBuyerUseCase:
    return CreateBuyerUseCase(_ddl_commands_unit_of_work_factory())


@dataclass(frozen=True)
class SellerResolutionRead:
    status: ResolutionStatus
    candidates: list[SellerSummary] | None = None


async def resolve_seller(seller_name: str) -> SellerResolutionRead:
    async with get_sessionmaker()() as session:
        resolution = await SellerResolutionService(
            build_seller_repository(session)
        ).resolve(seller_name)
        candidates = (
            [SellerSummary.model_validate(role) for role in resolution.candidates]
            if resolution.candidates is not None
            else None
        )
        return SellerResolutionRead(status=resolution.status, candidates=candidates)


async def resolve_seller_by_id(seller_role_id: str) -> SellerRole | None:
    async with get_sessionmaker()() as session:
        return await SellerResolutionService(build_seller_repository(session)).resolve_by_id(
            seller_role_id
        )


def build_update_seller_use_case() -> UpdateSellerUseCase:
    return UpdateSellerUseCase(_ddl_commands_unit_of_work_factory())


def build_create_seller_use_case() -> CreateSellerUseCase:
    return CreateSellerUseCase(_ddl_commands_unit_of_work_factory())


async def search_organizations(term: str) -> list[Organization]:
    async with get_sessionmaker()() as session:
        return await build_organization_repository(session).search_by_name(term)


async def resolve_organization(attio_id: str) -> Organization | None:
    async with get_sessionmaker()() as session:
        return await build_organization_repository(session).get_by_id_with_roles(attio_id)
