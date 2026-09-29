"""Ephemeral prompt shown when an approval finds deal(s) already in Attio
for the buyer+seller pair — the approver picks promote or create new."""

import uuid

from slack_sdk.models.blocks import ActionsBlock, Block, SectionBlock
from slack_sdk.models.blocks.block_elements import ButtonElement

from app.modules.matching_engine.api.slack.schemas import DealChoiceValue
from app.modules.matching_engine.domain.matching.deals import ExistingDeal
from app.modules.notifications import sanitize_mrkdwn

# Slack allows 5 buttons per actions block; two are reserved for create/cancel.
_MAX_PROMOTE_BUTTONS = 3


def _describe(deal: ExistingDeal) -> str:
    stage = deal.stage or "no stage"
    link = f" (<{deal.web_url}|open in Attio>)" if deal.web_url else ""
    return f"• *{sanitize_mrkdwn(deal.name)}* — {stage}{link}"


def build_existing_deal_prompt_blocks(
    match_result_id: uuid.UUID, deals: list[ExistingDeal]
) -> list[Block]:
    deals = deals[:_MAX_PROMOTE_BUTTONS]
    listing = "\n".join(_describe(d) for d in deals)
    buttons = [
        ButtonElement(
            text=f"Promote {sanitize_mrkdwn(d.name)}"[:75],
            action_id=f"promote_existing_deal_{i}",
            style="primary",
            value=DealChoiceValue(
                match_result_id=match_result_id,
                resolution="promote_existing",
                existing_deal_id=d.attio_id,
            ).model_dump_json(),
        )
        for i, d in enumerate(deals)
    ]
    buttons.append(
        ButtonElement(
            text="Create new deal",
            action_id="create_new_deal",
            value=DealChoiceValue(
                match_result_id=match_result_id, resolution="create_new"
            ).model_dump_json(),
        )
    )
    buttons.append(ButtonElement(text="Cancel", action_id="cancel_deal_choice", value="cancel"))
    return [
        SectionBlock(
            text=(
                "*Attio already has a deal for this buyer and seller:*\n"
                f"{listing}\n"
                "Promote an existing deal to Qualified, or create a new one?"
            )
        ),
        ActionsBlock(elements=buttons),
    ]
