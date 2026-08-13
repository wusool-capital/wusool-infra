"""`/find-match <buyer name>` (§3-4). Thin adapter: parse/validate the
payload, resolve the buyer (fast — a single lookup, not a long-running
call), then either open a disambiguation modal or dispatch the expensive
matching workflow (Bedrock + scoring + persistence) to the background task
runner. Never blocks the Slack ack on Bedrock/DB work.
"""

import logging

from slack_bolt.async_app import AsyncApp

from app.modules.buyers.dependencies import resolve_buyer
from app.modules.slack.match_dispatch import run_match_and_post
from app.modules.slack.views.buyer_selection import build_buyer_selection_modal
from app.shared.idempotency import InMemoryIdempotencyStore
from app.shared.tasks import InProcessTaskRunner

logger = logging.getLogger(__name__)

_idempotency_store = InMemoryIdempotencyStore()
_task_runner = InProcessTaskRunner()


def register(app: AsyncApp) -> None:
    @app.command("/find-match")
    async def handle_find_match(ack, command, client):  # noqa: ANN001
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

        resolution = await resolve_buyer(buyer_name)

        if resolution.status == "none":
            await client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=f"No buyer found for '{buyer_name}'. Try a different name.",
            )
            return

        if resolution.status == "multiple":
            assert resolution.candidates is not None
            await client.views_open(
                trigger_id=command["trigger_id"],
                view=build_buyer_selection_modal(
                    resolution.candidates, requested_by=user_id, channel_id=channel_id
                ),
            )
            return

        assert resolution.buyer is not None
        buyer_role_id = resolution.buyer.buyer_role_id
        _task_runner.run(
            lambda: run_match_and_post(buyer_role_id, user_id, channel_id),
            name=f"find-match:{buyer_role_id}",
        )
