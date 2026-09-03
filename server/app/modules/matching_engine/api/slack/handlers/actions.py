"""Buyer-selection modal submission, "View Full Analysis", and
Approve/Reject button actions (§4, §21-24). Thin adapters: parse the Slack
payload, validate the id format, call the application use case, translate
the result back into a Slack message. Every action re-validates against the
database — Slack payload state is never trusted on its own (§24).
"""

import json
import logging
import uuid

from slack_bolt.async_app import AsyncApp

from app.modules.matching_engine.api.dependencies import (
    build_approve_match_use_case,
    build_match_analysis_use_case,
    build_match_run_view_use_case,
    build_reject_match_use_case,
    run_match_and_post,
    to_match_analysis_schema,
)
from app.modules.matching_engine.api.slack.views.full_analysis import build_full_analysis_blocks
from app.modules.matching_engine.api.slack.views.match_result import (
    build_match_result_blocks_from_view,
)
from app.modules.matching_engine.application.approvals import (
    InvalidTransitionError,
    MatchNotFoundError,
)
from app.modules.utilities import InProcessTaskRunner
from app.modules.utilities.persistence.idempotency import InMemoryIdempotencyStore

logger = logging.getLogger(__name__)

_task_runner = InProcessTaskRunner()
_submission_idempotency_store = InMemoryIdempotencyStore()


def register(app: AsyncApp) -> None:
    @app.view("buyer_selection_modal")
    async def handle_buyer_selection_submission(ack, body, view):  # noqa: ANN001
        await ack()

        view_id = view.get("id")
        if view_id:
            idempotency_key = f"buyer_selection_submission:{view_id}"
            if _submission_idempotency_store.seen(idempotency_key):
                logger.info(
                    "buyer_selection_duplicate_delivery_skipped key=%s",
                    idempotency_key,
                    extra={"key": idempotency_key},
                )
                return
            _submission_idempotency_store.mark(idempotency_key)

        metadata = json.loads(view.get("private_metadata") or "{}")
        requested_by = metadata.get("requested_by") or body.get("user", {}).get("id")
        channel_id = metadata.get("channel_id")
        if not channel_id:
            return

        selected = view["state"]["values"]["buyer_role_id"]["selected_buyer"]["selected_option"]
        buyer_role_id = selected["value"]

        _task_runner.run(
            lambda: run_match_and_post(buyer_role_id, requested_by, channel_id),
            name=f"find-match:{buyer_role_id}",
        )

    @app.action("view_full_analysis")
    async def handle_view_full_analysis(ack, body, client):  # noqa: ANN001
        await ack()

        action = body["actions"][0]
        run_id_raw = action.get("value")
        channel_id = body["channel"]["id"]
        user_id = body["user"]["id"]

        try:
            run_id = uuid.UUID(run_id_raw)
        except (ValueError, TypeError):
            await client.chat_postEphemeral(
                channel=channel_id, user=user_id, text="Invalid analysis reference."
            )
            return

        analysis = await build_match_analysis_use_case().execute(run_id)
        if analysis is None:
            await client.chat_postEphemeral(
                channel=channel_id, user=user_id, text="No analysis found for this run."
            )
            return

        await client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text="Full match analysis",
            blocks=build_full_analysis_blocks(to_match_analysis_schema(analysis)),
        )

    @app.action("approve_match")
    async def handle_approve_match(ack, body, client, respond):  # noqa: ANN001
        await ack()
        await _handle_decision(body, client, respond, decision="approve")

    @app.action("reject_match")
    async def handle_reject_match(ack, body, client, respond):  # noqa: ANN001
        await ack()
        await _handle_decision(body, client, respond, decision="reject")

    @app.action("view_web_lead_source")
    async def handle_view_web_lead_source(ack):  # noqa: ANN001
        # A `url` button still sends an interaction payload Slack requires
        # this app to acknowledge, even though the browser opens the link
        # independently — no server-side action needed beyond the ack.
        await ack()


async def _handle_decision(body: dict, client, respond, decision: str) -> None:  # noqa: ANN001
    action = body["actions"][0]
    match_result_id_raw = action.get("value")
    channel_id = body["channel"]["id"]
    user_id = body["user"]["id"]

    try:
        match_result_id = uuid.UUID(match_result_id_raw)
    except (ValueError, TypeError):
        await client.chat_postEphemeral(
            channel=channel_id, user=user_id, text="Invalid match reference."
        )
        return

    use_case = (
        build_approve_match_use_case() if decision == "approve" else build_reject_match_use_case()
    )

    try:
        result = await use_case.execute(match_result_id, user_id)
    except MatchNotFoundError:
        await client.chat_postEphemeral(
            channel=channel_id, user=user_id, text="This match could not be found."
        )
        return
    except InvalidTransitionError:
        await client.chat_postEphemeral(
            channel=channel_id, user=user_id, text="This match has already been reviewed."
        )
        return

    await client.chat_postEphemeral(
        channel=channel_id,
        user=user_id,
        text=f"Match with {result.seller_org_name} {result.status.lower()} by <@{user_id}>.",
    )

    # Update the original message in place so a decided candidate's buttons
    # stop looking clickable (§23 — a repeat action must not appear possible).
    view = await build_match_run_view_use_case().execute(uuid.UUID(result.run_id))
    if view is not None:
        await respond(
            replace_original=True,
            text=f"Match results for {view.buyer_org_name}",
            blocks=build_match_result_blocks_from_view(view),
        )
