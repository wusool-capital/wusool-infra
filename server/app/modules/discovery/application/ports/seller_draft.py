"""The write-adjacent seam: `ddl_commands` implements this by opening its
own prefilled `/add-seller` modal (`providers/discovery/seller_draft_adapter.py`)
— this module never renders Slack views or writes anything itself, it only
hands over a `SellerDraft`.
"""

from typing import Protocol

from app.modules.discovery.domain.drafts import SellerDraft


class SellerDraftPort(Protocol):
    async def open_confirm_form(
        self, *, trigger_id: str, draft: SellerDraft, channel_id: str, requested_by: str
    ) -> None: ...
