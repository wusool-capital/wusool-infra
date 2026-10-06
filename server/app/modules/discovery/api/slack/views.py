"""Block Kit builders only, no logic. `build_possible_duplicate_blocks`
renders leads that fuzzy-matched an existing CRM organization and so were
*not* auto-created — each gets a "View on Maps" link (`lead.source_url`,
opened by Slack directly — no handler registered) and an "Add as seller"
button, `action_id="discover_add_seller"` (registered in `handlers.py`),
carrying an opaque token for the lead's draft as the button value — resolved
back server-side on click (see `api/dependencies.encode_draft`/`decode_draft`).
Two buttons per lead means `ActionsBlock`, not a `SectionBlock` accessory —
Slack allows only one accessory per section.

`build_needs_review_blocks` renders one lead whose website couldn't be
confirmed, styled like `enrichment`'s proposal message. Its "Review & Save"
button is `discover_review_seller` (value: the stored review's place id), or
`discover_add_seller` with a draft token when the review couldn't be stored.
"""

from collections.abc import Sequence

from slack_sdk.models.blocks import ActionsBlock, Block, ContextBlock, DividerBlock, SectionBlock
from slack_sdk.models.blocks.basic_components import MarkdownTextObject
from slack_sdk.models.blocks.block_elements import ButtonElement

from app.modules.discovery.api.dependencies import encode_draft
from app.modules.discovery.domain.drafts import DraftValue, draft_from_lead
from app.modules.discovery.domain.outcome import PossibleDuplicate, UnverifiedSeller
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
                        value=encode_draft(draft_from_lead(lead)),
                    ),
                ]
            )
        )
    return blocks


# Slack rejects a section over 3000 chars; value and rationale are capped
# separately, and the form still gets the full value.
_MAX_VALUE_CHARS = 300


def _render(value: DraftValue) -> str:
    text = ", ".join(value) if isinstance(value, list) else str(value)
    if len(text) > _MAX_VALUE_CHARS:
        text = text[:_MAX_VALUE_CHARS].rstrip() + "…"
    return sanitize_mrkdwn(text)


def build_needs_review_blocks(unverified: UnverifiedSeller) -> list[Block]:
    draft = unverified.draft
    title = f"*Website check for {sanitize_mrkdwn(draft.org_name)}*"
    if draft.source_urls:
        title += f" · <{draft.source_urls[0]}|View on Maps>"
    websites = [f"Google Maps: {_render(unverified.maps_website or 'none')}"] + [
        f"{sanitize_mrkdwn(provider)}: {_render(website or 'none')}"
        for provider, website in unverified.provider_websites
    ]
    blocks: list[Block] = [
        SectionBlock(text=title),
        DividerBlock(),
        SectionBlock(text="*website*\n" + "\n".join(websites)),
    ]
    blocks.extend(
        SectionBlock(
            text=(
                f"*{value.field_name}*\n"
                f"Proposed: {_render(value.value)}\n"
                f"Confidence: {value.confidence:.0%} — {_render(value.rationale)}"
            )
        )
        for value in unverified.values
    )
    # A stored review survives restarts; the draft token is the fallback.
    if unverified.review_id:
        action_id, value = "discover_review_seller", unverified.review_id
    else:
        action_id, value = "discover_add_seller", encode_draft(draft)
    blocks.append(DividerBlock())
    blocks.append(
        SectionBlock(
            text=(
                "Couldn't confirm this is the same company, so nothing was saved. "
                "Review these values in the add form before they're saved."
            ),
            accessory=ButtonElement(
                action_id=action_id, text="Review & Save", style="primary", value=value
            ),
        )
    )
    return blocks
