"""Step 1 of `/add-seller`/`/add-buyer`: search-before-create. Shows every
organization the typed name fuzzy-matched, each labeled with whether it
already has the role kind being added, plus a bailout option to create a
brand new organization instead. One shared modal for both kinds — `kind`
travels in `private_metadata` rather than the callback_id, since the
selection UI itself doesn't differ.

Picking an org that already has the target role isn't blocked here (its
`seller_role`/`buyer_role` isn't loaded far enough to filter cheaply against
in a Slack option list) — the submission handler in `actions.py` re-checks
the freshly-loaded org and stops with an "already exists" message rather
than silently overwriting.
"""

import json

from ddl_commands.shared.database.models.organization import Organization

NEW_ORGANIZATION_VALUE = "__new__"


def build_organization_selection_modal(
    candidates: list[Organization],
    *,
    kind: str,
    search_term: str,
    requested_by: str,
    channel_id: str,
) -> dict:
    options = []
    for org in candidates:
        has_role = (org.seller_role if kind == "seller" else org.buyer_role) is not None
        suffix = f" (already has a {kind} role)" if has_role else ""
        options.append(
            {
                "text": {"type": "plain_text", "text": f"{org.name}{suffix}"[:75]},
                "value": org.attio_id,
            }
        )
    options.append(
        {
            "text": {"type": "plain_text", "text": "None of these — create new organization"},
            "value": NEW_ORGANIZATION_VALUE,
        }
    )

    return {
        "type": "modal",
        "callback_id": "organization_selection_modal",
        "private_metadata": json.dumps(
            {
                "kind": kind,
                "search_term": search_term,
                "requested_by": requested_by,
                "channel_id": channel_id,
            }
        ),
        "title": {"type": "plain_text", "text": f"Add {kind}: organization"},
        "submit": {"type": "plain_text", "text": "Continue"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Found {len(candidates)} organization(s) matching *{search_term}*. "
                    "Attach the new role to one of these, or create a new organization.",
                },
            },
            {
                "type": "input",
                "block_id": "organization_id",
                "label": {"type": "plain_text", "text": "Organization"},
                "element": {
                    "type": "static_select",
                    "action_id": "selected_organization",
                    "options": options,
                    "initial_option": options[0],
                },
            },
        ],
    }
