"""Seller resolution semantics — mirrors `BuyerResolutionService` exactly."""

from dataclasses import dataclass
from typing import Literal

from app.modules.sellers.infrastructure.models import SellerRole
from app.modules.sellers.infrastructure.repositories import SellerRepository
from app.modules.sellers.schemas import SellerSummary

ResolutionStatus = Literal["none", "single", "multiple"]


@dataclass(frozen=True)
class SellerResolution:
    status: ResolutionStatus
    candidates: list[SellerSummary] | None = None


class SellerResolutionService:
    def __init__(self, seller_repository: SellerRepository) -> None:
        self._sellers = seller_repository

    async def resolve(
        self, seller_name: str, *, include_removed: bool = False
    ) -> SellerResolution:
        matches = await self._sellers.search_by_organization_name(
            seller_name, include_removed=include_removed
        )
        if not matches:
            return SellerResolution(status="none")

        status: ResolutionStatus = "single" if len(matches) == 1 else "multiple"
        return SellerResolution(
            status=status,
            candidates=[SellerSummary.model_validate(role) for role in matches],
        )

    async def resolve_by_id(self, seller_role_id: str) -> SellerRole | None:
        return await self._sellers.get_with_organization(seller_role_id)
