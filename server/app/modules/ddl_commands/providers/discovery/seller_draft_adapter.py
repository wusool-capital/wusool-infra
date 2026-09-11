"""Implements `discovery.SellerDraftPort` by opening the real `/add-seller`
form, prefilled with the draft's values (`seller_add_form.py`'s `prefill`
parameter) — the submission then goes through the ordinary
`handle_seller_add_form_submission` -> `SellerService.create_seller` path
unchanged; this module gains no new create logic for discovery, only a
prefilled starting point for the existing one.

Values not in a `select`/`multi_select_text` field's fixed vocabulary are
dropped here (never passed through as free text) — Slack silently drops an
unmatched `select` initial_option and degrades `multi_select_text` to a
free-text box (see `dynamic_fields.render_field_block`), so normalizing
before prefill keeps the rendered form predictable either way.
"""

from typing import Any

from app.modules.ddl_commands.api.dependencies import search_organizations
from app.modules.ddl_commands.api.organizations import ORGANIZATION_FIELDS_BY_NAME
from app.modules.ddl_commands.api.sellers import SELLER_ROLE_FIELDS_BY_NAME
from app.modules.ddl_commands.api.slack.views.organization_selection import (
    build_organization_selection_modal,
)
from app.modules.ddl_commands.api.slack.views.seller_add_form import build_seller_add_form_modal
from app.modules.ddl_commands.config import get_settings
from app.modules.discovery import SellerDraft
from app.modules.notifications import get_slack_client


def _normalize(values: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for name, value in values.items():
        spec = SELLER_ROLE_FIELDS_BY_NAME.get(name) or ORGANIZATION_FIELDS_BY_NAME.get(name)
        if spec is None or value is None:
            continue
        if spec.kind == "select" and value not in spec.options:
            continue
        if spec.kind == "multi_select_text":
            kept = [v for v in value if v in spec.options] if isinstance(value, list) else []
            if not kept:
                continue
            normalized[name] = kept
            continue
        normalized[name] = value
    return normalized


class DdlCommandsSellerDraftAdapter:
    async def open_confirm_form(
        self, *, trigger_id: str, draft: SellerDraft, channel_id: str, requested_by: str
    ) -> None:
        client = get_slack_client(get_settings().slack_bot_token)
        prefill = _normalize(draft.values)

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
