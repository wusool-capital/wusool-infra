"""Block Kit builders only, no logic. `build_possible_duplicate_blocks`
renders leads that fuzzy-matched an existing CRM organization and so were
*not* auto-created — each gets a "View on Maps" link (`lead.source_url`,
opened by Slack directly — no handler registered) and an "Add as seller"
button, `action_id="discover_add_seller"` (registered in `handlers.py`),
carrying an opaque token for the lead as the button value — resolved back
server-side on click (see `api/dependencies.encode_lead`/`decode_lead`). Two
buttons per lead means `ActionsBlock`, not a `SectionBlock` accessory — Slack
allows only one accessory per section.
"""

from collections.abc import Sequence

from slack_sdk.models.blocks import ActionsBlock, Block, ContextBlock, DividerBlock, SectionBlock
from slack_sdk.models.blocks.basic_components import MarkdownTextObject
from slack_sdk.models.blocks.block_elements import ButtonElement

from app.modules.discovery.api.dependencies import encode_lead
from app.modules.discovery.domain.outcome import PossibleDuplicate
from app.modules.notifications import sanitize_mrkdwn


def build_possible_duplicate_blocks(duplicates: Sequence[PossibleDuplicate]) -> list[Block]:
    if not duplicates:
        return []

    blocks: list[Block] = [
        ContextBlock(
            elements=[
                MarkdownTextObject(
                    text=(
                        f":warning: *{len(duplicates)} possible duplicate(s)* — not created. "
                        "A similarly named organization is already in the CRM; "
                        "add one only if it is a different company."
                    )
                )
            ]
        ),
        DividerBlock(),
    ]
    for rank, duplicate in enumerate(duplicates, start=1):
        lead = duplicate.lead
        detail = lead.address or lead.category or "No further details available."
        text = f"*{rank}. {sanitize_mrkdwn(lead.name)}*\n{sanitize_mrkdwn(detail)}"
        if lead.website:
            text += f"\n{sanitize_mrkdwn(lead.website)}"
        text += f"\n_Possibly the same as *{sanitize_mrkdwn(duplicate.existing_org_name)}*_"
        blocks.append(SectionBlock(text=text))
        blocks.append(
            ActionsBlock(
                elements=[
                    ButtonElement(
                        action_id="view_web_lead_source",
                        text="View on Maps",
                        url=lead.source_url,
                    ),
                    ButtonElement(
                        action_id="discover_add_seller",
                        text="Add as seller",
                        value=encode_lead(lead),
                    ),
                ]
            )
        )
    return blocks
