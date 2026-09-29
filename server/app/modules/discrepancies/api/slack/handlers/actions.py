"""Buyer-picker modal submission for `/check-buyer` — thin adapter: parse
the Slack payload, call the application use case, post the result. Every
action re-validates against the buyer-criteria Port — Slack payload state
is never trusted on its own.
"""

import json
import logging

from slack_bolt.async_app import AsyncApp
from slack_bolt.context.ack.async_ack import AsyncAck

from app.modules.discrepancies.api.dependencies import check_buyer_by_id
from app.modules.discrepancies.api.slack.views.report import build_discrepancy_blocks
from app.modules.discrepancies.bootstrap import build_slack_notifier
from app.modules.notifications import SlackViewSubmissionPayload
from app.modules.utilities import get_shared_idempotency_store, get_shared_task_runner

logger = logging.getLogger(__name__)

_task_runner = get_shared_task_runner()
_submission_idempotency_store = get_shared_idempotency_store()


def register(app: AsyncApp) -> None:
    @app.view("discrepancy_buyer_picker_modal")
    async def handle_buyer_picker_submission(
        ack: AsyncAck, view: SlackViewSubmissionPayload
    ) -> None:
        await ack()

        view_id = view.get("id")
        if view_id:
            idempotency_key = f"check_buyer_submission:{view_id}"
            if _submission_idempotency_store.seen(idempotency_key):
                logger.info(
                    "check_buyer_duplicate_delivery_skipped key=%s",
                    idempotency_key,
                    extra={"key": idempotency_key},
                )
                return
            _submission_idempotency_store.mark(idempotency_key)

        metadata = json.loads(view.get("private_metadata") or "{}")
        channel_id = metadata.get("channel_id")
        if not channel_id:
            return

        values = view["state"]["values"]
        selected = values["buyer_role_id"]["selected_buyer"]["selected_option"]
        buyer_role_id = selected["value"]
        context_input = values.get("advisor_context", {}).get("context_text")
        context_text = (context_input.get("value") or "").strip() if context_input else ""

        _task_runner.run(
            lambda: _check_and_post(buyer_role_id, context_text or None, channel_id),
            name=f"check-buyer:{buyer_role_id}",
        )


async def _check_and_post(buyer_role_id: str, context_text: str | None, channel_id: str) -> None:
    notifier = build_slack_notifier()
    try:
        result = await check_buyer_by_id(buyer_role_id, context_text)
        if result is None:
            await notifier.post_message(channel=channel_id, text="Buyer not found.")
            return
        await notifier.post_message(
            channel=channel_id, text=result.message, blocks=build_discrepancy_blocks(result)
        )
    except Exception:
        logger.exception("check_buyer_dispatch_failed", extra={"buyer_role_id": buyer_role_id})
        await notifier.post_message(
            channel=channel_id, text="Discrepancy check failed unexpectedly. Please try again."
        )
