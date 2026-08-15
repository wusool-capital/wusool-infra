"""`/edit-seller`'s pre-filled edit form. A single modal handles both a
normal edit and restoring an archived row — see `restore_confirmation_block`
and `SellerUpdate`'s docstring for why restoring needs its own explicit,
required confirmation rather than riding along on a routine edit.
"""

import json

from app.modules.sellers.infrastructure.models import SellerRole
from app.modules.slack.views.form_values import (
    date_input_block,
    money_input_blocks,
    number_input_block,
    restore_confirmation_block,
    text_input_block,
)


def build_seller_edit_form_modal(role: SellerRole, *, requested_by: str, channel_id: str) -> dict:
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
            text_input_block("outreach_tier", "Outreach tier", role.outreach_tier),
            text_input_block("appetite_signal", "Appetite signal", role.appetite_signal),
            text_input_block(
                "relationship_status", "Relationship status", role.relationship_status
            ),
            *money_input_blocks("est_revenue", "Est. revenue", role.est_revenue),
            *money_input_blocks("est_ebitda", "Est. EBITDA", role.est_ebitda),
            *money_input_blocks("owner_salary", "Owner salary", role.owner_salary),
            *money_input_blocks("valuation_low", "Valuation (low)", role.valuation_low),
            *money_input_blocks("valuation_mid", "Valuation (mid)", role.valuation_mid),
            *money_input_blocks("valuation_high", "Valuation (high)", role.valuation_high),
            text_input_block("sell_timeline", "Sell timeline", role.sell_timeline),
            number_input_block("readiness_score", "Readiness score (0-100)", role.readiness_score),
            text_input_block("readiness_band", "Readiness band", role.readiness_band),
            text_input_block("intake_source", "Intake source", role.intake_source),
            date_input_block("last_attempt_date", "Last attempt date", role.last_attempt_date),
            text_input_block(
                "last_attempt_channel", "Last attempt channel", role.last_attempt_channel
            ),
            text_input_block(
                "last_attempt_outcome",
                "Last attempt outcome",
                role.last_attempt_outcome,
                multiline=True,
            ),
            number_input_block(
                "lead_quality_score", "Lead quality score (0-100)", role.lead_quality_score
            ),
            date_input_block("re_engage_date", "Re-engage date", role.re_engage_date),
        ]
    )

    if archived:
        blocks.append(restore_confirmation_block())

    return {
        "type": "modal",
        "callback_id": "seller_edit_form_modal",
        "private_metadata": json.dumps(
            {
                "seller_role_id": str(role.id),
                "org_name": role.organization.name,
                "requested_by": requested_by,
                "channel_id": channel_id,
                "archived": archived,
            }
        ),
        "title": {"type": "plain_text", "text": "Edit seller"},
        "submit": {"type": "plain_text", "text": "Restore & Save" if archived else "Save"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": blocks,
    }
