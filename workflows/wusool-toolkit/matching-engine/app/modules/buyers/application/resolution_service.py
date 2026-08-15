"""Buyer resolution semantics (§4). The repository owns lookup mechanics
(`search_by_organization_name`'s ILIKE strategy); this service owns what to
do with 0/1/many results — kept out of the Slack handler entirely.

Every non-empty result always populates `candidates` (length 1 for a single
match) — the Slack layer always shows the "choose the right buyer"
confirmation modal, even for one strong match, rather than silently
proceeding straight into the expensive matching workflow. `status` still
distinguishes single vs. multiple for callers that care.
"""

from dataclasses import dataclass, replace
from typing import Literal

from app.modules.buyers.application.mappers import to_buyer_context
from app.modules.buyers.domain.value_objects import BuyerContext
from app.modules.buyers.infrastructure.repositories import BuyerRepository
from app.modules.buyers.schemas import BuyerSummary
from app.modules.matching.infrastructure.meeting_repository import MeetingRepository

ResolutionStatus = Literal["none", "single", "multiple"]


@dataclass(frozen=True)
class BuyerResolution:
    status: ResolutionStatus
    candidates: list[BuyerSummary] | None = None


class BuyerResolutionService:
    def __init__(
        self, buyer_repository: BuyerRepository, meeting_repository: MeetingRepository | None = None
    ) -> None:
        self._buyers = buyer_repository
        self._meetings = meeting_repository

    async def resolve(self, buyer_name: str) -> BuyerResolution:
        matches = await self._buyers.search_by_organization_name(buyer_name)

        if not matches:
            return BuyerResolution(status="none")

        status: ResolutionStatus = "single" if len(matches) == 1 else "multiple"
        return BuyerResolution(
            status=status,
            candidates=[BuyerSummary.model_validate(role) for role in matches],
        )

    async def resolve_by_id(self, buyer_role_id: str) -> BuyerContext | None:
        """Used after a Slack buyer-selection modal submission."""
        role = await self._buyers.get_with_organization(buyer_role_id)
        if role is None:
            return None

        context = to_buyer_context(role)
        if self._meetings is not None:
            notes = await self._meetings.get_recent_by_org(context.org_attio_id)
            context = replace(context, meeting_notes=notes)
        return context
