"""Where leads held back for a website review wait: lets a later run skip
them and keeps their "Review & Save" button working across restarts.
Implemented by `persistence/review_store.py`.
"""

from datetime import datetime
from typing import Protocol

from app.modules.discovery.domain.drafts import SellerDraft
from app.modules.discovery.domain.outcome import UnverifiedSeller


class ReviewStore(Protocol):
    async def pending_place_ids(self, place_ids: list[str], *, flagged_since: datetime) -> set[str]:
        """Only leads whose card was posted, flagged on or after `flagged_since`."""
        ...

    async def add(self, unverified: UnverifiedSeller) -> None:
        """Upserts by `unverified.draft.source_place_id`, which must be set;
        a re-flag restarts the clock and clears `posted`."""
        ...

    async def mark_posted(self, place_id: str) -> None: ...

    async def get_draft(self, place_id: str) -> SellerDraft | None: ...
