"""Step 2 of the edit flow, for both `/edit-seller` and `/edit-buyer`: after
resolving the target, the operator picks which fields to edit — from both
`organizations` and the role table — before seeing a form. Keeps the actual
edit form small and focused instead of showing ~20 fields at once regardless
of what the operator actually came to change.
"""

import json

from app.modules.ddl_commands.api.organizations import ORGANIZATION_FIELDS
from app.modules.ddl_commands.api.schemas import FieldSpec
from app.modules.utilities.domain.text import sanitize_mrkdwn

# Slack caps a `checkboxes` element at 10 options, and both role field lists
# are already past it (15 seller, 11 buyer). Over the cap Slack rejects the
# whole `response_action: "update"` view: the modal shows "We had some trouble
# connecting", while our side logs a clean 200 and never raises. Same
# `selected_options` payload shape either way, so `extract_selected_fields`
# below is unchanged — but a multi-select holds 100.
_MAX_OPTIONS = 100


def _field_options(fields: tuple[FieldSpec, ...]) -> list[dict]:
    assert len(fields) <= _MAX_OPTIONS, f"{len(fields)} options exceeds Slack's {_MAX_OPTIONS}"
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
                    "text": f"Which fields do you want to edit for *{sanitize_mrkdwn(org_name)}*?",
                },
            },
            {
                "type": "input",
                "block_id": "org_fields",
                "optional": True,
                "label": {"type": "plain_text", "text": "Organization"},
                "element": {
                    "type": "multi_static_select",
                    "action_id": "selected_org_fields",
                    "placeholder": {"type": "plain_text", "text": "Pick fields to edit"},
                    "options": _field_options(ORGANIZATION_FIELDS),
                },
            },
            {
                "type": "input",
                "block_id": "role_fields",
                "optional": True,
                "label": {"type": "plain_text", "text": kind.capitalize() + " profile"},
                "element": {
                    "type": "multi_static_select",
                    "action_id": "selected_role_fields",
                    "placeholder": {"type": "plain_text", "text": "Pick fields to edit"},
                    "options": _field_options(role_fields),
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
