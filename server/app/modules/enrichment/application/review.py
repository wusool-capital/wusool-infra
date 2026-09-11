"""Hands a proposal off for review — this module never writes anything
itself; `EnrichmentReviewPort` opens the real edit form.
"""

from app.modules.enrichment.application.base import ServiceBase
from app.modules.enrichment.domain.proposals import EnrichmentProposal


class ReviewMixin(ServiceBase):
    async def open_review_form(
        self, *, trigger_id: str, proposal: EnrichmentProposal, channel_id: str, requested_by: str
    ) -> None:
        if not proposal.values:
            return
        await self._review_port.open_review_form(
            trigger_id=trigger_id,
            target=proposal.target,
            values=proposal.values,
            channel_id=channel_id,
            requested_by=requested_by,
        )
