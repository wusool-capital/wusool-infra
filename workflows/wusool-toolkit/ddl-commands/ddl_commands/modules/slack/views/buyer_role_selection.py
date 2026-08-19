"""Buyer disambiguation modal for `/edit-buyer` — mirrors
`seller_role_selection.py::build_seller_selection_modal` exactly, buyer-typed.

Named (and callback_id'd) `buyer_role_selection`, not `buyer_selection` —
matching-engine's own `/find-match` already has an unrelated
`buyer_selection_modal` (its own match-target disambiguation). Since both
bots now run in one process on one `AsyncApp`, a shared callback_id would
mean two Bolt listeners registered for the same view submission with no way
to tell which payload belongs to which handler.
"""

import json

from ddl_commands.modules.buyers.schemas import BuyerSummary


def build_buyer_selection_modal(
    candidates: list[BuyerSummary], *, requested_by: str, channel_id: str
) -> dict:
    options = []
    for candidate in candidates:
        org = candidate.organization
        detail_bits = [b for b in (org.hq_country, ", ".join(org.sector_focus) or None) if b]
        detail = f" ({', '.join(detail_bits)})" if detail_bits else ""
        options.append(
            {
                "text": {"type": "plain_text", "text": f"{org.name}{detail}"[:75]},
                "value": str(candidate.id),
            }
        )

    label = (
        "Confirm this is the right buyer to edit"
        if len(options) == 1
        else "Choose the right buyer to edit"
    )

    return {
        "type": "modal",
        "callback_id": "buyer_role_selection_modal",
        # See `seller_role_selection.py` — `org_names` exists so the submission
        # handler can `ack()` inside Slack's 3s window without a database query.
        "private_metadata": json.dumps(
            {
                "requested_by": requested_by,
                "channel_id": channel_id,
                "org_names": {str(c.id): c.organization.name for c in candidates},
            }
        ),
        "title": {"type": "plain_text", "text": "Confirm buyer"},
        "submit": {"type": "plain_text", "text": "Continue"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "buyer_role_id",
                "label": {"type": "plain_text", "text": label},
                "element": {
                    "type": "static_select",
                    "action_id": "selected_buyer",
                    "options": options,
                    "initial_option": options[0],
                },
            }
        ],
    }
