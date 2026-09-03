"""`/edit-seller`'s dynamic edit form — step 3 of the flow: only the fields
the operator picked in the field-picker modal are shown, pre-filled from
the current row (organization fields from `org`, seller fields from `role`).
"""

import json

from app.models import Organization, SellerRole
from app.modules.ddl_commands.api.organizations import ORGANIZATION_FIELDS_BY_NAME
from app.modules.ddl_commands.api.sellers import (
    GATED_SELLER_ROLE_FIELDS,
    SELLER_ROLE_FIELDS_BY_NAME,
)
from app.modules.ddl_commands.api.slack.views.dynamic_fields import render_field_block
from app.modules.ddl_commands.api.slack.views.form_values import confirmation_checkbox_block


def build_seller_edit_form_modal(
    role: SellerRole,
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
        spec = SELLER_ROLE_FIELDS_BY_NAME[name]
        blocks.append(render_field_block(spec, getattr(role, name)))

    gated_selected = GATED_SELLER_ROLE_FIELDS & set(selected_role_fields)
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
        "callback_id": "seller_edit_form_modal",
        "private_metadata": json.dumps(
            {
                "seller_role_id": str(role.id),
                "org_attio_id": org.attio_id,
                "org_name": org.name,
                "requested_by": requested_by,
                "channel_id": channel_id,
                "selected_org_fields": selected_org_fields,
                "selected_role_fields": selected_role_fields,
            }
        ),
        "title": {"type": "plain_text", "text": "Edit seller"},
        "submit": {"type": "plain_text", "text": "Save"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": blocks,
    }
