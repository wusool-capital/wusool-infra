"""`/check-buyer <buyer name>` — a standalone discrepancy check, so an
advisor can ask about a buyer's data quality without going through
`/find-match` at all. Mirrors `matching_engine`'s own `/find-match` command
handler shape: ack first, idempotency-guard on `trigger_id`, usage message
on empty text, always shows the confirm-picker modal (even for one match).
"""

import logging

from slack_bolt.async_app import AsyncApp
from slack_bolt.context.ack.async_ack import AsyncAck
from slack_sdk.web.async_client import AsyncWebClient

from app.modules.discrepancies.api.dependencies import search_buyers
from app.modules.discrepancies.api.slack.views.buyer_picker import build_buyer_picker_modal
from app.modules.notifications import SlackCommandPayload, build_notice_modal, open_loading_modal
from app.modules.utilities import get_shared_idempotency_store

logger = logging.getLogger(__name__)

_idempotency_store = get_shared_idempotency_store()


def register(app: AsyncApp) -> None:
    @app.command("/check-buyer")
    async def handle_check_buyer(
        ack: AsyncAck, command: SlackCommandPayload, client: AsyncWebClient
    ) -> None:
        await ack()
        idempotency_key = f"check_buyer:{command.get('trigger_id')}"
        if _idempotency_store.seen(idempotency_key):
            logger.info(
                "check_buyer_duplicate_delivery_skipped key=%s",
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
                channel=channel_id, user=user_id, text="Usage: `/check-buyer <buyer name>`"
            )
            return

        view_id = await open_loading_modal(
            client, trigger_id=command["trigger_id"], title="Check buyer"
        )
        candidates = await search_buyers(buyer_name)

        if not candidates:
            await client.views_update(
                view_id=view_id,
                view=build_notice_modal(
                    "Check buyer", f"No buyer found for '{buyer_name}'. Try a different name."
                ),
            )
            return

        await client.views_update(
            view_id=view_id,
            view=build_buyer_picker_modal(candidates, requested_by=user_id, channel_id=channel_id),
        )
