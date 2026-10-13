from app.modules.discovery.api.slack.review_card import (
    ReviewCard,
    mark_card_added,
    store_review_card,
)
from app.modules.notifications import SlackInteractionBody


def test_mark_card_added_replaces_only_the_clicked_block() -> None:
    title = {"type": "section", "block_id": "title", "text": {"type": "mrkdwn", "text": "x"}}
    button = {"type": "section", "block_id": "review", "text": {"type": "mrkdwn", "text": "y"}}
    card = ReviewCard(
        channel_id="C1", ts="1.2", text="t", block_id="review", blocks=[title, button]
    )

    blocks = mark_card_added(card, "U1")

    assert blocks[0] == title
    assert blocks[1]["type"] == "context"
    assert "✅ *ADDED* by <@U1>" in str(blocks[1])


def test_store_review_card_returns_none_when_the_click_has_no_message() -> None:
    body: SlackInteractionBody = {
        "channel": {"id": "C1"},
        "actions": [{"action_id": "discover_review_seller", "block_id": "b1"}],
    }

    assert store_review_card(body) is None
