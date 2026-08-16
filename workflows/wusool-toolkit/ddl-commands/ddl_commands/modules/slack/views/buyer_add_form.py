"""`/add-buyer`'s form — mirrors `seller_add_form.py` exactly, buyer-typed."""

import json

from ddl_commands.modules.buyers.field_spec import BUYER_ROLE_FIELDS
from ddl_commands.modules.slack.views.dynamic_fields import render_field_block
from ddl_commands.modules.slack.views.form_values import text_input_block
from ddl_commands.shared.database.models.organization import Organization
from ddl_commands.shared.organization_field_spec import ORGANIZATION_FIELDS


def build_buyer_add_form_modal(
    *,
    org: Organization | None,
    requested_by: str,
    channel_id: str,
    prefill_name: str = "",
) -> dict:
    is_new_org = org is None
    blocks: list[dict] = []
    if is_new_org:
        name_block = text_input_block("name", "Organization name", prefill_name or None)
        name_block["optional"] = False
        blocks.append(name_block)
    else:
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"Attaching this buyer role to *{org.name}*."},
            }
        )

    for spec in ORGANIZATION_FIELDS:
        current = getattr(org, spec.name) if org is not None else None
        blocks.append(render_field_block(spec, current, block_id_prefix="org_"))

    for spec in BUYER_ROLE_FIELDS:
        blocks.append(render_field_block(spec, None))

    return {
        "type": "modal",
        "callback_id": "buyer_add_form_modal",
        "private_metadata": json.dumps(
            {
                "is_new_org": is_new_org,
                "org_attio_id": None if org is None else org.attio_id,
                "org_name": None if org is None else org.name,
                "requested_by": requested_by,
                "channel_id": channel_id,
            }
        ),
        "title": {"type": "plain_text", "text": "Add buyer"},
        "submit": {"type": "plain_text", "text": "Save"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": blocks,
    }
