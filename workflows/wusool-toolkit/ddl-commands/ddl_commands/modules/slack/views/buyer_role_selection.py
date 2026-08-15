"""Buyer disambiguation modal for `/edit-buyer` and `/remove-buyer` — mirrors
`seller_role_selection.py::build_seller_selection_modal` exactly, buyer-typed.

Named (and callback_id'd) `buyer_role_selection`, not `buyer_selection` —
matching-engine's own `/find-match` already has an unrelated
`buyer_selection_modal` (its own match-target disambiguation). Since both
bots now run in one process on one `AsyncApp`, a shared callback_id would
mean two Bolt listeners registered for the same view submission with no way
to tell which payload belongs to which handler.
"""

import json
from typing import Literal

from ddl_commands.modules.buyers.schemas import BuyerSummary


def build_buyer_selection_modal(
    candidates: list[BuyerSummary],
    *,
    requested_by: str,
    channel_id: str,
    intent: Literal["edit", "remove"],
) -> dict:
    options = []
    for candidate in candidates:
        org = candidate.organization
        detail_bits = [b for b in (org.hq_country, ", ".join(org.sector_focus) or None) if b]
        detail = f" ({', '.join(detail_bits)})" if detail_bits else ""
        removed_suffix = " (removed)" if candidate.removed_at is not None else ""
        options.append(
            {
                "text": {
                    "type": "plain_text",
                    "text": f"{org.name}{detail}{removed_suffix}"[:75],
                },
                "value": str(candidate.id),
            }
        )

    action_word = "edit" if intent == "edit" else "remove"
    label = (
        f"Confirm this is the right buyer to {action_word}"
        if len(options) == 1
        else f"Choose the right buyer to {action_word}"
    )

    return {
        "type": "modal",
        "callback_id": "buyer_role_selection_modal",
        "private_metadata": json.dumps(
            {"requested_by": requested_by, "channel_id": channel_id, "intent": intent}
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
