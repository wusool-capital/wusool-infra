"""Step 2b of `/edit-buyer`, shown only when the operator ticks "Also set a
new key contact" in the field-picker (`field_picker.py`) — a small form to
create the Person who becomes the buyer role's key contact. Always creates a
brand-new person; there is no search-and-pick-an-existing-one path here.

`name` is required, same idiom `seller_add_form.py`/`buyer_add_form.py` use
for an org's `name` — everything else is optional, matching the same
all-optional-except-name convention every creation form in this bot uses.
"""

import json

from ddl_commands.modules.buyers.person_field_spec import PERSON_FIELDS
from ddl_commands.modules.slack.views.dynamic_fields import render_field_block
from ddl_commands.modules.slack.views.form_values import text_input_block


def build_key_contact_create_form_modal(
    *,
    buyer_role_id: str,
    org_attio_id: str,
    org_name: str,
    selected_org_fields: list[str],
    selected_role_fields: list[str],
    requested_by: str,
    channel_id: str,
) -> dict:
    name_block = text_input_block("name", "Contact name", None)
    name_block["optional"] = False
    blocks: list[dict] = [name_block]
    for spec in PERSON_FIELDS:
        blocks.append(render_field_block(spec, None))

    return {
        "type": "modal",
        "callback_id": "buyer_key_contact_create_modal",
        "private_metadata": json.dumps(
            {
                "buyer_role_id": buyer_role_id,
                "org_attio_id": org_attio_id,
                "org_name": org_name,
                "selected_org_fields": selected_org_fields,
                "selected_role_fields": selected_role_fields,
                "requested_by": requested_by,
                "channel_id": channel_id,
            }
        ),
        "title": {"type": "plain_text", "text": "New key contact"},
        "submit": {"type": "plain_text", "text": "Continue"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": blocks,
    }
