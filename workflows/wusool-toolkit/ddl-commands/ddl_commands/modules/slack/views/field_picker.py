"""Step 2 of the edit flow, for both `/edit-seller` and `/edit-buyer`: after
resolving the target, the operator picks which fields to edit — from both
`organizations` and the role table — before seeing a form. Keeps the actual
edit form small and focused instead of showing ~20 fields at once regardless
of what the operator actually came to change.
"""

import json

from ddl_commands.shared.organization_field_spec import ORGANIZATION_FIELDS, FieldSpec


def _checkbox_options(fields: tuple[FieldSpec, ...]) -> list[dict]:
    return [{"text": {"type": "plain_text", "text": f.label}, "value": f.name} for f in fields]


def build_field_picker_modal(
    *,
    kind: str,
    role_id: str,
    org_name: str,
    requested_by: str,
    channel_id: str,
    role_fields: tuple[FieldSpec, ...],
) -> dict:
    role_id_key = f"{kind}_role_id"
    return {
        "type": "modal",
        "callback_id": f"{kind}_field_picker_modal",
        "private_metadata": json.dumps(
            {
                role_id_key: role_id,
                "org_name": org_name,
                "requested_by": requested_by,
                "channel_id": channel_id,
            }
        ),
        "title": {"type": "plain_text", "text": f"Edit {kind}: fields"},
        "submit": {"type": "plain_text", "text": "Continue"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Which fields do you want to edit for *{org_name}*?",
                },
            },
            {
                "type": "input",
                "block_id": "org_fields",
                "optional": True,
                "label": {"type": "plain_text", "text": "Organization"},
                "element": {
                    "type": "checkboxes",
                    "action_id": "selected_org_fields",
                    "options": _checkbox_options(ORGANIZATION_FIELDS),
                },
            },
            {
                "type": "input",
                "block_id": "role_fields",
                "optional": True,
                "label": {"type": "plain_text", "text": kind.capitalize() + " profile"},
                "element": {
                    "type": "checkboxes",
                    "action_id": "selected_role_fields",
                    "options": _checkbox_options(role_fields),
                },
            },
        ],
    }


def extract_selected_fields(values: dict) -> tuple[list[str], list[str]]:
    org_selected = values.get("org_fields", {}).get("selected_org_fields", {}).get(
        "selected_options", []
    )
    role_selected = values.get("role_fields", {}).get("selected_role_fields", {}).get(
        "selected_options", []
    )
    return (
        [o["value"] for o in org_selected],
        [o["value"] for o in role_selected],
    )
