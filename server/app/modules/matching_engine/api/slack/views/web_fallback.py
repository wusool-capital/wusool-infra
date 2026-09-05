"""Web-fallback result message — shown instead of the normal ranked-CRM-
candidate message when no CRM seller's score clears the qualifying
threshold. Block Kit builders only, no logic. Leads are unverified and
never persisted (§ web_search module docstring), so the message says so
plainly rather than presenting them as equivalent to a CRM match.
"""

from slack_sdk.models.blocks import Block, ContextBlock, DividerBlock, SectionBlock
from slack_sdk.models.blocks.basic_components import MarkdownTextObject
from slack_sdk.models.blocks.block_elements import ButtonElement

from app.modules.matching_engine.domain.web_search import WebSourcedLead
from app.modules.notifications import sanitize_mrkdwn


def build_web_fallback_blocks(buyer_org_name: str, leads: list[WebSourcedLead]) -> list[Block]:
    blocks: list[Block] = [
        SectionBlock(text=f"*Buyer:*\n{buyer_org_name}"),
        ContextBlock(
            elements=[
                MarkdownTextObject(
                    text=(
                        f"⚠️ No qualifying CRM sellers found — showing {len(leads)} "
                        "web-sourced lead(s). *Not yet in CRM, unverified.*"
                    )
                )
            ]
        ),
        DividerBlock(),
    ]

    for rank, lead in enumerate(leads, start=1):
        detail = lead.address or lead.category or "No further details available."
        name = sanitize_mrkdwn(lead.name)
        text = f"*{rank}. {name}*\n{sanitize_mrkdwn(detail)}"
        if lead.category and lead.address:
            category = sanitize_mrkdwn(lead.category)
            address = sanitize_mrkdwn(lead.address)
            text = f"*{rank}. {name}*\n{category}\n{address}"

        blocks.append(
            SectionBlock(
                text=text,
                accessory=ButtonElement(
                    action_id="view_web_lead_source",
                    text="View Source",
                    url=lead.source_url,
                ),
            )
        )

    return blocks
