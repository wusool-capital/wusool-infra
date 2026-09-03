"""Step 1 of `/add-seller`/`/add-buyer`: search-before-create. Shows every
organization the typed name fuzzy-matched, each labeled with whether it
already has the role kind being added, plus a bailout option to create a
brand new organization instead. One shared modal for both kinds — `kind`
travels in `private_metadata` rather than the callback_id, since the
selection UI itself doesn't differ.

Picking an org that already has the target role isn't blocked here (its
`seller_roles`/`buyer_roles` isn't loaded far enough to filter cheaply against
in a Slack option list) — the submission handler in `actions.py` re-checks
the freshly-loaded org and stops with an "already exists" message rather
than silently overwriting.
"""

import json

from slack_sdk.models.blocks import InputBlock, SectionBlock
from slack_sdk.models.blocks.basic_components import Option
from slack_sdk.models.blocks.block_elements import StaticSelectElement
from slack_sdk.models.views import View

from app.models import Organization
from app.modules.notifications import sanitize_mrkdwn

NEW_ORGANIZATION_VALUE = "__new__"


def build_organization_selection_modal(
    candidates: list[Organization],
    *,
    kind: str,
    search_term: str,
    requested_by: str,
    channel_id: str,
) -> View:
    options = []
    for org in candidates:
        roles = org.seller_roles if kind == "seller" else org.buyer_roles
        has_role = any(r.is_active for r in roles)
        suffix = f" (already has a {kind} role)" if has_role else ""
        options.append(Option(value=org.attio_id, text=f"{org.name}{suffix}"[:75]))
    options.append(
        Option(value=NEW_ORGANIZATION_VALUE, text="None of these — create new organization")
    )

    return View(
        type="modal",
        callback_id="organization_selection_modal",
        private_metadata=json.dumps(
            {
                "kind": kind,
                "search_term": search_term,
                "requested_by": requested_by,
                "channel_id": channel_id,
                "candidate_names": [org.name for org in candidates],
            }
        ),
        title=f"Add {kind}: organization",
        submit="Continue",
        close="Cancel",
        blocks=[
            SectionBlock(
                text=f"Found {len(candidates)} organization(s) matching "
                f"*{sanitize_mrkdwn(search_term)}*. Attach the new role to one of these, "
                "or create a new organization."
            ),
            InputBlock(
                block_id="organization_id",
                label="Organization",
                element=StaticSelectElement(
                    action_id="selected_organization", options=options, initial_option=options[0]
                ),
            ),
        ],
    )
