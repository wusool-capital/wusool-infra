"""Implements `enrichment.EnrichmentReviewPort` by opening this module's own
real `/edit-seller`/`/edit-buyer` modal, prefilled with the proposed values
(`seller_form.py`/`buyer_form.py`'s `prefill` parameter) — the submission
then goes through the ordinary `seller_edit_form_modal`/`buyer_edit_form_modal`
write path unchanged; this module gains no new write logic for enrichment,
only a prefilled starting point for the existing one.

Values not in a `select`/`multi_select_text` field's fixed vocabulary are
dropped here (never passed through as free text) — same reasoning as
`providers/discovery/seller_draft_adapter.py::_normalize`.

The dependency edge points this way on purpose (`ddl_commands ->
enrichment`, never the reverse) so `enrichment` never needs to know Attio
or Postgres exist — see `enrichment/__init__.py`'s docstring.
"""

from typing import Any

from app.modules.ddl_commands.api.buyers import BUYER_ROLE_FIELDS_BY_NAME
from app.modules.ddl_commands.api.dependencies import resolve_buyer_by_id, resolve_seller_by_id
from app.modules.ddl_commands.api.organizations import ORGANIZATION_FIELDS_BY_NAME
from app.modules.ddl_commands.api.schemas import FieldSpec
from app.modules.ddl_commands.api.sellers import SELLER_ROLE_FIELDS_BY_NAME
from app.modules.ddl_commands.api.slack.views.buyer_form import build_buyer_edit_form_modal
from app.modules.ddl_commands.api.slack.views.seller_form import build_seller_edit_form_modal
from app.modules.ddl_commands.config import get_settings
from app.modules.enrichment import EnrichmentTarget, EnrichmentTargetKind, ProposedFieldValue
from app.modules.notifications import get_slack_client

_ROLE_FIELDS_BY_NAME = {
    EnrichmentTargetKind.SELLER: SELLER_ROLE_FIELDS_BY_NAME,
    EnrichmentTargetKind.BUYER: BUYER_ROLE_FIELDS_BY_NAME,
}


def _normalize(values: dict[str, Any], fields_by_name: dict[str, FieldSpec]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for name, value in values.items():
        spec = fields_by_name.get(name)
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


class DdlCommandsReviewAdapter:
    async def open_review_form(
        self,
        *,
        trigger_id: str,
        target: EnrichmentTarget,
        values: tuple[ProposedFieldValue, ...],
        channel_id: str,
        requested_by: str,
    ) -> None:
        if not values:
            return

        role_fields_by_name = _ROLE_FIELDS_BY_NAME[target.kind]
        combined_fields_by_name = {**role_fields_by_name, **ORGANIZATION_FIELDS_BY_NAME}
        prefill = _normalize({v.field_name: v.proposed for v in values}, combined_fields_by_name)
        if not prefill:
            return

        role_names = [name for name in prefill if name in role_fields_by_name]
        org_names = [name for name in prefill if name in ORGANIZATION_FIELDS_BY_NAME]

        client = get_slack_client(get_settings().slack_bot_token)

        if target.kind is EnrichmentTargetKind.SELLER:
            role = await resolve_seller_by_id(str(target.role_id))
            if role is None:
                return
            view = build_seller_edit_form_modal(
                role,
                role.organization,
                selected_org_fields=org_names,
                selected_role_fields=role_names,
                requested_by=requested_by,
                channel_id=channel_id,
                prefill=prefill,
            )
        else:
            role = await resolve_buyer_by_id(str(target.role_id))
            if role is None:
                return
            view = build_buyer_edit_form_modal(
                role,
                role.organization,
                selected_org_fields=org_names,
                selected_role_fields=role_names,
                requested_by=requested_by,
                channel_id=channel_id,
                prefill=prefill,
            )

        await client.views_open(trigger_id=trigger_id, view=view)
