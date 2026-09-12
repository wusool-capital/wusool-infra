"""The hand-off seam: `ddl_commands` implements this by opening its own
real `/edit-seller`/`/edit-buyer` modal, prefilled with the proposed
values (`providers/enrichment/review_adapter.py`) — the submission then
goes through that module's ordinary edit path unchanged. This module
never writes to Attio or Postgres itself; it only ever proposes and hands
the proposal off for review.
"""

from typing import Protocol

from app.modules.enrichment.domain.proposals import ProposedFieldValue
from app.modules.enrichment.domain.targets import EnrichmentTarget


class EnrichmentReviewPort(Protocol):
    async def open_review_form(
        self,
        *,
        trigger_id: str,
        target: EnrichmentTarget,
        values: tuple[ProposedFieldValue, ...],
        channel_id: str,
        requested_by: str,
    ) -> None: ...
