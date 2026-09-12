"""Hands a `SellerDraft` to `SellerDraftPort` — this module renders nothing
itself; `ddl_commands` opens the actual prefilled `/add-seller` modal.
"""

from app.modules.discovery.application.base import ServiceBase
from app.modules.discovery.domain.drafts import SellerDraft


class ConfirmMixin(ServiceBase):
    async def open_confirm_form(
        self, *, trigger_id: str, draft: SellerDraft, channel_id: str, requested_by: str
    ) -> None:
        await self._seller_draft_port.open_confirm_form(
            trigger_id=trigger_id, draft=draft, channel_id=channel_id, requested_by=requested_by
        )
