"""Seller disambiguation modal for `/edit-seller` and `/remove-seller` — the
same "confirm/choose the right seller" shape matching-engine's
`buyer_selection.py::build_buyer_selection_modal` already uses for
`/find-match`, extended with an `intent` (edit vs remove) and an
`(archived)` label on any archived candidate.
"""

import json
from typing import Literal

from app.modules.sellers.schemas import SellerSummary


def build_seller_selection_modal(
    candidates: list[SellerSummary],
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
        archived_suffix = " (archived)" if candidate.archived_at is not None else ""
        options.append(
            {
                "text": {
                    "type": "plain_text",
                    "text": f"{org.name}{detail}{archived_suffix}"[:75],
                },
                "value": str(candidate.id),
            }
        )

    action_word = "edit" if intent == "edit" else "remove"
    label = (
        f"Confirm this is the right seller to {action_word}"
        if len(options) == 1
        else f"Choose the right seller to {action_word}"
    )

    return {
        "type": "modal",
        "callback_id": "seller_selection_modal",
        "private_metadata": json.dumps(
            {"requested_by": requested_by, "channel_id": channel_id, "intent": intent}
        ),
        "title": {"type": "plain_text", "text": "Confirm seller"},
        "submit": {"type": "plain_text", "text": "Continue"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "seller_role_id",
                "label": {"type": "plain_text", "text": label},
                "element": {
                    "type": "static_select",
                    "action_id": "selected_seller",
                    "options": options,
                    "initial_option": options[0],
                },
            }
        ],
    }
