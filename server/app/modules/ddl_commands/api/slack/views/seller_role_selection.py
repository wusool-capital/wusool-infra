"""Seller disambiguation modal for `/edit-seller` — the same
"confirm/choose the right seller" shape matching-engine's own
`buyer_selection.py::build_buyer_selection_modal` uses for `/find-match`.

Named (and callback_id'd) `seller_role_selection`, not `seller_selection` —
kept consistent with `buyer_role_selection.py`'s naming even though no
seller-side collision exists today, to avoid the same latent trap later.
"""

import json

from app.modules.ddl_commands.api.sellers import SellerSummary


def build_seller_selection_modal(
    candidates: list[SellerSummary], *, requested_by: str, channel_id: str
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
        "Confirm this is the right seller to edit"
        if len(options) == 1
        else "Choose the right seller to edit"
    )

    return {
        "type": "modal",
        "callback_id": "seller_role_selection_modal",
        # `org_names` carries each candidate's organization name forward so the
        # submission handler can build the next modal without a database round
        # trip. It has only 3s to `ack()` before Slack abandons the request, and
        # the name is the only thing it needed that query for.
        "private_metadata": json.dumps(
            {
                "requested_by": requested_by,
                "channel_id": channel_id,
                "org_names": {str(c.id): c.organization.name for c in candidates},
            }
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
