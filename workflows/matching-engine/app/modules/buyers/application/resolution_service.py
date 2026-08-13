"""Buyer resolution semantics (§4). The repository owns lookup mechanics
(`search_by_organization_name`'s ILIKE strategy); this service owns what to
do with 0/1/many results — kept out of the Slack handler entirely.
"""

from dataclasses import dataclass
from typing import Literal

from app.modules.buyers.application.mappers import to_buyer_context
from app.modules.buyers.domain.value_objects import BuyerContext
from app.modules.buyers.infrastructure.repositories import BuyerRepository
from app.modules.buyers.schemas import BuyerSummary

ResolutionStatus = Literal["none", "single", "multiple"]


@dataclass(frozen=True)
class BuyerResolution:
    status: ResolutionStatus
    buyer: BuyerContext | None = None
    candidates: list[BuyerSummary] | None = None


class BuyerResolutionService:
    def __init__(self, buyer_repository: BuyerRepository) -> None:
        self._buyers = buyer_repository

    async def resolve(self, buyer_name: str) -> BuyerResolution:
        matches = await self._buyers.search_by_organization_name(buyer_name)

        if not matches:
            return BuyerResolution(status="none")

        if len(matches) == 1:
            role = await self._buyers.get_with_organization(str(matches[0].id))
            assert role is not None
            return BuyerResolution(status="single", buyer=to_buyer_context(role))

        return BuyerResolution(
            status="multiple",
            candidates=[BuyerSummary.model_validate(role) for role in matches],
        )

    async def resolve_by_id(self, buyer_role_id: str) -> BuyerContext | None:
        """Used after a Slack buyer-selection modal submission."""
        role = await self._buyers.get_with_organization(buyer_role_id)
        return to_buyer_context(role) if role is not None else None
