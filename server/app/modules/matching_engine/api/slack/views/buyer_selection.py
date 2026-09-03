"""Buyer confirmation modal (§4) — shown for every `/find-match <name>`
resolution that finds at least one candidate, even a single strong match.
Confirming before the expensive matching workflow runs is a deliberate
product choice, not just disambiguation for multiple matches. Block Kit
builders only, no logic.
"""

import json

from slack_sdk.models.blocks import InputBlock
from slack_sdk.models.blocks.basic_components import Option
from slack_sdk.models.blocks.block_elements import StaticSelectElement
from slack_sdk.models.views import View

from app.modules.matching_engine.api.buyers import BuyerSummary


def build_buyer_selection_modal(
    candidates: list[BuyerSummary], *, requested_by: str, channel_id: str
) -> View:
    options = []
    for candidate in candidates:
        org = candidate.organization
        detail_bits = [b for b in (org.hq_country, ", ".join(org.sector_focus) or None) if b]
        detail = f" ({', '.join(detail_bits)})" if detail_bits else ""
        options.append(Option(value=str(candidate.id), text=f"{org.name}{detail}"[:75]))

    label = "Confirm this is the right buyer" if len(options) == 1 else "Choose the right buyer"

    return View(
        type="modal",
        callback_id="buyer_selection_modal",
        private_metadata=json.dumps({"requested_by": requested_by, "channel_id": channel_id}),
        title="Confirm buyer",
        submit="Find matches",
        close="Cancel",
        blocks=[
            InputBlock(
                block_id="buyer_role_id",
                label=label,
                element=StaticSelectElement(
                    action_id="selected_buyer",
                    options=options,
                    initial_option=options[0],
                ),
            )
        ],
    )
