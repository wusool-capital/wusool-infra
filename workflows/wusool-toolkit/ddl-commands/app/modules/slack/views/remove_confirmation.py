"""Shared "archive or cancel" confirmation blocks for `/remove-seller` and
`/remove-buyer` — an ephemeral message with a live match-count and two
buttons, not a second chained modal (a deliberate choice, see plan.md).
Button `value` is always a bare role-id UUID string, matching matching-engine's
existing "never a JSON envelope" convention.
"""

from typing import Literal

from app.modules.slack.views.mrkdwn import sanitize_mrkdwn


def build_remove_confirmation_blocks(
    role_id: str, org_name: str, match_count: int, *, kind: Literal["seller", "buyer"]
) -> list[dict]:
    if match_count:
        plural = "s" if match_count != 1 else ""
        count_text = f"{match_count} match record{plural} reference this {kind}."
    else:
        count_text = f"No match records reference this {kind}."

    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{sanitize_mrkdwn(org_name)}*\n{count_text}",
            },
        },
        {
            "type": "actions",
            "block_id": f"{kind}_remove_actions_{role_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Archive"},
                    "style": "danger",
                    "action_id": f"archive_{kind}",
                    "value": role_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Cancel"},
                    "action_id": f"cancel_{kind}",
                    "value": role_id,
                },
            ],
        },
    ]
