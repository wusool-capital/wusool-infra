"""Hands a `SellerDraft` to `SellerDraftPort` — this module renders nothing
itself; `ddl_commands` opens the actual prefilled `/add-seller` modal. A
stored website-review lead is loaded back from `ReviewStore` first.
"""

from app.modules.discovery.application.base import ServiceBase
from app.modules.discovery.domain.drafts import SellerDraft
from app.modules.utilities import NotFoundError


class ConfirmMixin(ServiceBase):
    async def open_confirm_form(
        self, *, trigger_id: str, draft: SellerDraft, channel_id: str, requested_by: str
    ) -> None:
        await self._seller_draft_port.open_confirm_form(
            trigger_id=trigger_id, draft=draft, channel_id=channel_id, requested_by=requested_by
        )

    async def open_review_form(
        self, *, trigger_id: str, review_id: str, channel_id: str, requested_by: str
    ) -> None:
        """Raises `NotFoundError` for an unknown review."""
        draft = await self._review_store.get_draft(review_id)
        if draft is None:
            raise NotFoundError(f"No discovery review {review_id!r}")
        await self.open_confirm_form(
            trigger_id=trigger_id, draft=draft, channel_id=channel_id, requested_by=requested_by
        )
