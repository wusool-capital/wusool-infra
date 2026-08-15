"""Buyer disambiguation modal for `/edit-buyer` and `/remove-buyer` — mirrors
`seller_selection.py::build_seller_selection_modal` exactly, buyer-typed.
"""

import json
from typing import Literal

from app.modules.buyers.schemas import BuyerSummary


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
        "callback_id": "buyer_selection_modal",
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
