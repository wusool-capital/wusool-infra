"""`/find-match <buyer name>` (§3-4). Thin adapter: parse/validate the
payload, resolve the buyer (fast — a single lookup, not a long-running
call), then always open the "confirm buyer" modal for any non-empty
result — even one strong match requires an explicit confirm before the
expensive matching workflow (Bedrock + scoring + persistence) runs. That
workflow itself is dispatched from the modal's submission handler
(`actions.py`), not here.
"""

import logging

from slack_bolt.async_app import AsyncApp
from slack_bolt.context.ack.async_ack import AsyncAck
from slack_sdk.web.async_client import AsyncWebClient

from app.modules.matching_engine.api.dependencies import resolve_buyer
from app.modules.matching_engine.api.slack.views.buyer_selection import (
    build_buyer_selection_modal,
)
from app.modules.notifications import (
    SlackCommandPayload,
    build_notice_modal,
    open_loading_modal,
)
from app.modules.utilities import get_shared_idempotency_store

logger = logging.getLogger(__name__)

_idempotency_store = get_shared_idempotency_store()


def register(app: AsyncApp) -> None:
    @app.command("/find-match")
    async def handle_find_match(
        ack: AsyncAck, command: SlackCommandPayload, client: AsyncWebClient
    ) -> None:
        await ack()

        # §28: Slack can retry slash-command delivery on a slow ack or
        # network blip. A retried delivery re-acks (above) and stops here —
        # the same interaction carries the same trigger_id.
        idempotency_key = f"find_match:{command.get('trigger_id')}"
        if _idempotency_store.seen(idempotency_key):
            logger.info(
                "find_match_duplicate_delivery_skipped key=%s",
                idempotency_key,
                extra={"key": idempotency_key},
            )
            return
        _idempotency_store.mark(idempotency_key)

        buyer_name = (command.get("text") or "").strip()
        channel_id = command["channel_id"]
        user_id = command["user_id"]

        if not buyer_name:
            await client.chat_postEphemeral(
                channel=channel_id, user=user_id, text="Usage: `/find-match <buyer name>`"
            )
            return

        view_id = await open_loading_modal(
            client, trigger_id=command["trigger_id"], title="Find match"
        )

        resolution = await resolve_buyer(buyer_name)

        if resolution.status == "none":
            await client.views_update(
                view_id=view_id,
                view=build_notice_modal(
                    "Find match", f"No buyer found for '{buyer_name}'. Try a different name."
                ),
            )
            return

        assert resolution.candidates is not None
        await client.views_update(
            view_id=view_id,
            view=build_buyer_selection_modal(
                resolution.candidates, requested_by=user_id, channel_id=channel_id
            ),
        )
