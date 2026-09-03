"""`/add-seller`'s form — step 2 (new org) or step 3 (attaching to an
existing org found by search) of the flow. Unlike `/edit-seller`'s
field-picker-then-form, every eligible field is shown at once, all optional
except `name` — see `ddl-commands/README.md` for why creation gets one form
instead of a picker.

No gated-field confirmation checkbox here: nothing is gated any more (#53
dropped `intake_source`, the only such field), and a brand new role has no
existing value to overwrite regardless.
"""

import json

from app.models import Organization
from app.modules.ddl_commands.api.organizations import ORGANIZATION_FIELDS
from app.modules.ddl_commands.api.sellers import SELLER_ROLE_FIELDS
from app.modules.ddl_commands.api.slack.views.dynamic_fields import render_field_block
from app.modules.ddl_commands.api.slack.views.form_values import text_input_block
from app.modules.notifications import sanitize_mrkdwn


def build_seller_add_form_modal(
    *,
    org: Organization | None,
    requested_by: str,
    channel_id: str,
    prefill_name: str = "",
    duplicate_candidates: list[str] | None = None,
) -> dict:
    is_new_org = org is None
    blocks: list[dict] = []
    if is_new_org:
        if duplicate_candidates:
            names = ", ".join(f"*{sanitize_mrkdwn(name)}*" for name in duplicate_candidates)
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f":warning: {len(duplicate_candidates)} similar organization(s) "
                            f"already exist: {names}. Continuing will create a new, separate "
                            "organization in Attio."
                        ),
                    },
                }
            )
        name_block = text_input_block("name", "Organization name", prefill_name or None)
        name_block["optional"] = False
        blocks.append(name_block)
    else:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Attaching this seller role to *{sanitize_mrkdwn(org.name)}*.",
                },
            }
        )

    for spec in ORGANIZATION_FIELDS:
        current = getattr(org, spec.name) if org is not None else None
        blocks.append(render_field_block(spec, current, block_id_prefix="org_"))

    for spec in SELLER_ROLE_FIELDS:
        blocks.append(render_field_block(spec, None))

    return {
        "type": "modal",
        "callback_id": "seller_add_form_modal",
        "private_metadata": json.dumps(
            {
                "is_new_org": is_new_org,
                "org_attio_id": None if org is None else org.attio_id,
                "org_name": None if org is None else org.name,
                "requested_by": requested_by,
                "channel_id": channel_id,
            }
        ),
        "title": {"type": "plain_text", "text": "Add seller"},
        "submit": {"type": "plain_text", "text": "Save"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": blocks,
    }
