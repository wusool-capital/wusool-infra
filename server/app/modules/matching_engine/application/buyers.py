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

from app.modules.matching_engine.application.base import ServiceBase
from app.modules.matching_engine.domain.buyers import BuyerContext

ResolutionStatus = Literal["none", "single", "multiple"]


@dataclass(frozen=True)
class BuyerCandidate:
    """Domain-level view of a single search result — the api/ layer's
    Pydantic schema is built from this, never directly from the ORM row.
    Fields are exactly what `buyer_selection.py`'s confirmation modal
    renders, not a blanket copy of every Organization column."""

    id: str
    org_attio_id: str
    org_name: str
    model: str | None
    mandate_status: str | None
    org_hq_country: str | None
    org_sector_focus: list[str]


@dataclass(frozen=True)
class BuyerResolution:
    status: ResolutionStatus
    candidates: list[BuyerCandidate] | None = None


class BuyersMixin(ServiceBase):
    async def resolve_buyer(self, buyer_name: str) -> BuyerResolution:
        matches = await self._buyers.search_by_organization_name(buyer_name)

        if not matches:
            return BuyerResolution(status="none")

        status: ResolutionStatus = "single" if len(matches) == 1 else "multiple"
        return BuyerResolution(
            status=status,
            candidates=[
                BuyerCandidate(
                    id=context.buyer_role_id,
                    org_attio_id=context.org_attio_id,
                    org_name=context.org_name,
                    model=context.model,
                    mandate_status=context.mandate_status,
                    org_hq_country=context.org_hq_country,
                    org_sector_focus=context.org_sector_focus,
                )
                for context in matches
            ],
        )

    async def resolve_buyer_by_id(self, buyer_role_id: str) -> BuyerContext | None:
        """Used after a Slack buyer-selection modal submission."""
        context = await self._buyers.get_with_organization(buyer_role_id)
        if context is None:
            return None

        if self._meetings is not None:
            notes = await self._meetings.get_recent_by_org(context.org_attio_id)
            context = replace(context, meeting_notes=notes)
        return context
