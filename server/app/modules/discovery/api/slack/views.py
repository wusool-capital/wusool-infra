"""Block Kit builders only, no logic. `build_lead_blocks` renders the
result of a lead search as a message — each lead gets a "View on Maps" link
(`lead.source_url`, opened by Slack directly — no handler registered, same
as any other URL button) and an "Add as seller" button,
`action_id="discover_add_seller"` (registered in `handlers.py`), carrying
the lead itself as the button value so the click needs no server-side
lookup to act on it (see `api/dependencies.encode_lead`). Two buttons per
lead means `ActionsBlock`, not a `SectionBlock` accessory — Slack allows
only one accessory per section.
"""

from slack_sdk.models.blocks import ActionsBlock, Block, ContextBlock, DividerBlock, SectionBlock
from slack_sdk.models.blocks.basic_components import MarkdownTextObject
from slack_sdk.models.blocks.block_elements import ButtonElement

from app.modules.discovery.api.dependencies import encode_lead
from app.modules.discovery.domain.leads import DiscoveredLead
from app.modules.notifications import sanitize_mrkdwn


def build_lead_blocks(leads: list[DiscoveredLead]) -> list[Block]:
    if not leads:
        return [SectionBlock(text="No potential sellers found from public sources.")]

    blocks: list[Block] = [
        ContextBlock(
            elements=[
                MarkdownTextObject(
                    text=(
                        f"Found {len(leads)} potential seller(s) from public sources. "
                        "*Not yet in CRM, unverified.*"
                    )
                )
            ]
        ),
        DividerBlock(),
    ]
    for rank, lead in enumerate(leads, start=1):
        detail = lead.address or lead.category or "No further details available."
        blocks.append(
            SectionBlock(text=f"*{rank}. {sanitize_mrkdwn(lead.name)}*\n{sanitize_mrkdwn(detail)}")
        )
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
