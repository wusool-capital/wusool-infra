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

`candidate_names`/`prefill` grow with search-result count and with however
many fields `discovery`'s hand-off populated — the same shape that overran
`enrichment`'s button `value` once its field set grew (see
`enrichment.api.slack.views.proposal_message`). `private_metadata`'s own
cap is more generous (3000 chars vs. a button's 2000) and today's org-search
`limit=10` keeps this well under it, but rather than rely on that never
changing, the two growable fields are stored server-side
(`utilities.get_shared_ephemeral_store`) the same way, and only a token
rides in `private_metadata`.
"""

import json

from slack_sdk.models.blocks import InputBlock, SectionBlock
from slack_sdk.models.blocks.basic_components import Option
from slack_sdk.models.blocks.block_elements import StaticSelectElement
from slack_sdk.models.views import View

from app.models import Organization
from app.modules.ddl_commands.api.schemas import PrefillValue
from app.modules.notifications import sanitize_mrkdwn
from app.modules.utilities import get_shared_ephemeral_store

NEW_ORGANIZATION_VALUE = "__new__"


def _encode_selection_payload(candidate_names: list[str], prefill: dict[str, PrefillValue]) -> str:
    return get_shared_ephemeral_store().put(
        json.dumps({"candidate_names": candidate_names, "prefill": prefill})
    )


def decode_selection_payload(token: str | None) -> tuple[list[str], dict[str, PrefillValue]]:
    """`(candidate_names, prefill)`, or `([], {})` for a missing, expired,
    or unknown token — this is the growable part of the modal's
    `private_metadata` (its own docstring explains why it's a token, not
    the values themselves). `token` is `str | None` (not just `str`) so a
    modal submitted mid-deploy — built by the previous version, before
    `payload_token` existed in this schema — degrades the same way an
    expired one does, instead of a `KeyError` out of the submission
    handler. Degrading to empty rather than raising: losing the "here's
    why your typed name didn't match" duplicate-candidates list or a
    `discovery` prefill is a worse form pre-filled slightly less usefully,
    not a broken submission the way a missing enrichment proposal would be.
    """
    if token is None:
        return [], {}
    payload = get_shared_ephemeral_store().get(token)
    if payload is None:
        return [], {}
    data = json.loads(payload)
    return data["candidate_names"], data["prefill"]


def build_organization_selection_modal(
    candidates: list[Organization],
    *,
    kind: str,
    search_term: str,
    requested_by: str,
    channel_id: str,
    prefill: dict[str, PrefillValue] | None = None,
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
                "payload_token": _encode_selection_payload(
                    [org.name for org in candidates], prefill or {}
                ),
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
