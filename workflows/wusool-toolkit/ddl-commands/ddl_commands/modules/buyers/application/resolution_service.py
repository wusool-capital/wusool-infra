"""Buyer resolution semantics. The repository owns lookup mechanics; this
service owns what to do with 0/1/many results — kept out of the Slack
handler entirely.

Every non-empty result always populates `candidates` (length 1 for a single
match) — the Slack layer always shows a "choose the right buyer" modal, even
for one strong match, mirroring matching-engine's `/find-match` convention.
"""

from dataclasses import dataclass
from typing import Literal

from ddl_commands.modules.buyers.infrastructure.repositories import BuyerRepository
from ddl_commands.modules.buyers.schemas import BuyerSummary
from wusool_db.models import BuyerRole

ResolutionStatus = Literal["none", "single", "multiple"]


@dataclass(frozen=True)
class BuyerResolution:
    status: ResolutionStatus
    candidates: list[BuyerSummary] | None = None


class BuyerResolutionService:
    def __init__(self, buyer_repository: BuyerRepository) -> None:
        self._buyers = buyer_repository

    async def resolve(self, buyer_name: str) -> BuyerResolution:
        matches = await self._buyers.search_by_organization_name(buyer_name)
        if not matches:
            return BuyerResolution(status="none")

        status: ResolutionStatus = "single" if len(matches) == 1 else "multiple"
        return BuyerResolution(
            status=status,
            candidates=[BuyerSummary.model_validate(role) for role in matches],
        )

    async def resolve_by_id(self, buyer_role_id: str) -> BuyerRole | None:
        """Used after a Slack buyer-selection modal submission. Returns the
        ORM row directly (organization eager-loaded) — this bot has no
        matching pipeline, so there's no need for a separate domain value
        object/mapper layer the way matching-engine has.
        """
        return await self._buyers.get_with_organization(buyer_role_id)
