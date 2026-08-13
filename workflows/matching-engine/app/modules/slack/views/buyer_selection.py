"""Buyer disambiguation modal (§4) — shown when `/find-match <name>` matches
more than one buyer. Block Kit builders only, no logic.
"""

import json

from app.modules.buyers.schemas import BuyerSummary


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

    return {
        "type": "modal",
        "callback_id": "buyer_selection_modal",
        "private_metadata": json.dumps({"requested_by": requested_by, "channel_id": channel_id}),
        "title": {"type": "plain_text", "text": "Select a buyer"},
        "submit": {"type": "plain_text", "text": "Find matches"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "buyer_role_id",
                "label": {"type": "plain_text", "text": "Multiple buyers matched — pick one"},
                "element": {
                    "type": "static_select",
                    "action_id": "selected_buyer",
                    "options": options,
                },
            }
        ],
    }
