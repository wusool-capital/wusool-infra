"""`/edit-buyer`'s pre-filled edit form — mirrors `seller_form.py` exactly,
buyer-typed.
"""

import json

from app.modules.buyers.infrastructure.models import BuyerRole
from app.modules.slack.views.form_values import (
    bool_select_block,
    money_input_blocks,
    number_input_block,
    restore_confirmation_block,
    text_input_block,
)


def build_buyer_edit_form_modal(role: BuyerRole, *, requested_by: str, channel_id: str) -> dict:
    archived = role.archived_at is not None

    blocks: list[dict] = []
    if archived:
        blocks.append(
            {
                "type": "section",
                "block_id": "restore_banner",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        ":warning: *This profile is archived.* Saving this form "
                        "will restore it and make it matchable again."
                    ),
                },
            }
        )

    blocks.extend(
        [
            text_input_block("model", "Model", role.model),
            text_input_block("mandate_status", "Mandate status", role.mandate_status),
            *money_input_blocks("ebitda_floor", "EBITDA floor", role.ebitda_floor),
            *money_input_blocks("check_size_min", "Check size (min)", role.check_size_min),
            *money_input_blocks("check_size_max", "Check size (max)", role.check_size_max),
            *money_input_blocks("ev_ceiling", "EV ceiling", role.ev_ceiling),
            text_input_block(
                "deal_structure_tolerance",
                "Deal structure tolerance",
                role.deal_structure_tolerance,
            ),
            text_input_block(
                "earnout_tolerance", "Earnout tolerance", role.earnout_tolerance
            ),
            bool_select_block("profitable_only", "Profitable only", role.profitable_only),
            text_input_block(
                "investment_strategy",
                "Investment strategy",
                role.investment_strategy,
                multiline=True,
            ),
            text_input_block("notes", "Notes", role.notes, multiline=True),
            text_input_block(
                "acquisition_enrichment",
                "Acquisition enrichment",
                role.acquisition_enrichment,
                multiline=True,
            ),
            number_input_block("deals_introduced", "Deals introduced", role.deals_introduced),
            number_input_block("deals_converted", "Deals converted", role.deals_converted),
        ]
    )

    if archived:
        blocks.append(restore_confirmation_block())

    return {
        "type": "modal",
        "callback_id": "buyer_edit_form_modal",
        "private_metadata": json.dumps(
            {
                "buyer_role_id": str(role.id),
                "org_name": role.organization.name,
                "requested_by": requested_by,
                "channel_id": channel_id,
                "archived": archived,
            }
        ),
        "title": {"type": "plain_text", "text": "Edit buyer"},
        "submit": {"type": "plain_text", "text": "Restore & Save" if archived else "Save"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": blocks,
    }
