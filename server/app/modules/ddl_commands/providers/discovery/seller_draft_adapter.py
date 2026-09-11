"""Implements `discovery.SellerDraftPort` by opening the real `/add-seller`
form, prefilled with the draft's values (`seller_add_form.py`'s `prefill`
parameter) — the submission then goes through the ordinary
`handle_seller_add_form_submission` -> `SellerService.create_seller` path
unchanged; this module gains no new create logic for discovery, only a
prefilled starting point for the existing one.
"""

from app.modules.ddl_commands.api.dependencies import search_organizations
from app.modules.ddl_commands.api.organizations import ORGANIZATION_FIELDS_BY_NAME
from app.modules.ddl_commands.api.sellers import SELLER_ROLE_FIELDS_BY_NAME
from app.modules.ddl_commands.api.slack.views.dynamic_fields import normalize_prefill
from app.modules.ddl_commands.api.slack.views.organization_selection import (
    build_organization_selection_modal,
)
from app.modules.ddl_commands.api.slack.views.seller_add_form import build_seller_add_form_modal
from app.modules.ddl_commands.config import get_settings
from app.modules.discovery import SellerDraft
from app.modules.notifications import get_slack_client

# `SellerDraft.values` (`discovery`'s own domain, `dict[str, Any]`) is the
# only prefill source with no `FieldKind` vocabulary of its own — every
# other caller of `normalize_prefill` builds `fields_by_name` from a typed
# `FieldSpec` source. Sellers only, so this can be a fixed combined dict
# rather than something threaded through per-call like `review_adapter.py`
# does for buyer/seller.
_SELLER_FIELDS_BY_NAME = {**SELLER_ROLE_FIELDS_BY_NAME, **ORGANIZATION_FIELDS_BY_NAME}


class DdlCommandsSellerDraftAdapter:
    async def open_confirm_form(
        self, *, trigger_id: str, draft: SellerDraft, channel_id: str, requested_by: str
    ) -> None:
        client = get_slack_client(get_settings().slack_bot_token)
        prefill = normalize_prefill(draft.values, _SELLER_FIELDS_BY_NAME)

        candidates = await search_organizations(draft.org_name)
        if candidates:
            await client.views_open(
                trigger_id=trigger_id,
                view=build_organization_selection_modal(
                    candidates,
                    kind="seller",
                    search_term=draft.org_name,
                    requested_by=requested_by,
                    channel_id=channel_id,
                    prefill=prefill,
                ),
            )
            return

        await client.views_open(
            trigger_id=trigger_id,
            view=build_seller_add_form_modal(
                org=None,
                requested_by=requested_by,
                channel_id=channel_id,
                prefill_name=draft.org_name,
                prefill=prefill,
            ),
        )
