"""`/edit-buyer`'s dynamic edit form — mirrors `seller_form.py` exactly,
buyer-typed.
"""

import json

from ddl_commands.modules.buyers.field_spec import (
    BUYER_ROLE_FIELDS_BY_NAME,
    GATED_BUYER_ROLE_FIELDS,
)
from ddl_commands.modules.buyers.infrastructure.models import BuyerRole
from ddl_commands.modules.slack.views.dynamic_fields import render_field_block
from ddl_commands.modules.slack.views.form_values import confirmation_checkbox_block
from ddl_commands.shared.database.models.organization import Organization
from ddl_commands.shared.organization_field_spec import ORGANIZATION_FIELDS_BY_NAME


def build_buyer_edit_form_modal(
    role: BuyerRole,
    org: Organization,
    *,
    selected_org_fields: list[str],
    selected_role_fields: list[str],
    requested_by: str,
    channel_id: str,
) -> dict:
    blocks: list[dict] = []
    for name in selected_org_fields:
        spec = ORGANIZATION_FIELDS_BY_NAME[name]
        blocks.append(render_field_block(spec, getattr(org, name), block_id_prefix="org_"))
    for name in selected_role_fields:
        spec = BUYER_ROLE_FIELDS_BY_NAME[name]
        blocks.append(render_field_block(spec, getattr(role, name)))

    gated_selected = GATED_BUYER_ROLE_FIELDS & set(selected_role_fields)
    if gated_selected:
        blocks.append(
            confirmation_checkbox_block(
                "gated_field_confirmation",
                "confirm_correction",
                "Confirm correction",
                "This is a correction to an existing value, not a routine edit",
            )
        )

    return {
        "type": "modal",
        "callback_id": "buyer_edit_form_modal",
        "private_metadata": json.dumps(
            {
                "buyer_role_id": str(role.id),
                "org_attio_id": org.attio_id,
                "org_name": org.name,
                "requested_by": requested_by,
                "channel_id": channel_id,
                "selected_org_fields": selected_org_fields,
                "selected_role_fields": selected_role_fields,
            }
        ),
        "title": {"type": "plain_text", "text": "Edit buyer"},
        "submit": {"type": "plain_text", "text": "Save"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": blocks,
    }
