"""Marks a website-check card as added once its "Review & Save" lands.

The card can't be rebuilt later (the review store keeps only the draft) and
the bot can't read channel history, so the clicked message's blocks are
stashed at click time and carried through the add-seller modals as a token.
"""

import logging

from pydantic import BaseModel, JsonValue, ValidationError
from slack_sdk.models.blocks import ContextBlock
from slack_sdk.models.blocks.basic_components import MarkdownTextObject

from app.modules.discovery.config import get_settings
from app.modules.notifications import SlackInteractionBody, get_slack_client
from app.modules.utilities import get_shared_ephemeral_store

logger = logging.getLogger(__name__)

# Slack's own block JSON, echoed back to `chat.update` untouched; parsing it
# through slack_sdk models could drop fields they don't cover.
SlackBlockJson = dict[str, JsonValue]


class _ClickedMessage(BaseModel):
    ts: str
    text: str
    blocks: list[SlackBlockJson]


class ReviewCard(BaseModel):
    channel_id: str
    ts: str
    text: str
    block_id: str
    blocks: list[SlackBlockJson]


def store_review_card(body: SlackInteractionBody) -> str | None:
    """`None` when the click can't be captured: the form must still open."""
    try:
        message = _ClickedMessage.model_validate(body["message"])
        card = ReviewCard(
            channel_id=body["channel"]["id"],
            ts=message.ts,
            text=message.text,
            block_id=body["actions"][0]["block_id"],
            blocks=message.blocks,
        )
    except (KeyError, ValidationError):
        logger.exception("review_card_capture_failed")
        return None
    # ponytail: in-memory, lost on restart; persist channel/ts on `discovery_reviews` if that bites.
    return get_shared_ephemeral_store().put(card.model_dump_json())


def mark_card_added(card: ReviewCard, added_by: str) -> list[SlackBlockJson]:
    """Swaps the clicked "Review & Save" section for who added it."""
    added = ContextBlock(elements=[MarkdownTextObject(text=f"✅ *ADDED* by <@{added_by}>")])
    return [added.to_dict() if b.get("block_id") == card.block_id else b for b in card.blocks]


async def mark_review_card_added(card_token: str, added_by: str) -> None:
    """A no-op for an expired token: the seller is saved either way."""
    payload = get_shared_ephemeral_store().get(card_token)
    if payload is None:
        logger.info("review_card_token_expired")
        return
    card = ReviewCard.model_validate_json(payload)
    client = get_slack_client(get_settings().slack_bot_token)
    await client.chat_update(
        channel=card.channel_id,
        ts=card.ts,
        text=card.text,
        blocks=mark_card_added(card, added_by),
    )
