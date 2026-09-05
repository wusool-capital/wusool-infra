"""`/edit-buyer`'s dynamic edit form — mirrors `seller_form.py` exactly,
buyer-typed.
"""

import json

from slack_sdk.models.blocks import Block
from slack_sdk.models.views import View

from app.models import BuyerRole, Organization
from app.modules.ddl_commands.api.buyers import (
    BUYER_ROLE_FIELDS_BY_NAME,
    GATED_BUYER_ROLE_FIELDS,
)
from app.modules.ddl_commands.api.organizations import ORGANIZATION_FIELDS_BY_NAME
from app.modules.ddl_commands.api.slack.views.dynamic_fields import render_field_block
from app.modules.ddl_commands.api.slack.views.form_values import confirmation_checkbox_block


def build_buyer_edit_form_modal(
    role: BuyerRole,
    org: Organization,
    *,
    selected_org_fields: list[str],
    selected_role_fields: list[str],
    requested_by: str,
    channel_id: str,
) -> View:
    blocks: list[Block] = []
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

    return View(
        type="modal",
        callback_id="buyer_edit_form_modal",
        private_metadata=json.dumps(
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
        title="Edit buyer",
        submit="Save",
        close="Cancel",
        blocks=blocks,
    )
