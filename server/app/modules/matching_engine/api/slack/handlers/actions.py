"""Buyer-selection modal submission, "View Full Analysis", and
Approve/Reject button actions (§4, §21-24). Thin adapters: parse the Slack
payload, validate the id format, call the application use case, translate
the result back into a Slack message. Every action re-validates against the
database — Slack payload state is never trusted on its own (§24).
"""

import json
import logging
import re
import uuid

from pydantic import ValidationError
from slack_bolt.async_app import AsyncApp
from slack_bolt.context.ack.async_ack import AsyncAck
from slack_bolt.context.respond.async_respond import AsyncRespond
from slack_sdk.web.async_client import AsyncWebClient

from app.modules.matching_engine.api.dependencies import (
    matching_engine_service,
    run_match_and_post,
    to_match_analysis_schema,
    trigger_seller_discovery,
)
from app.modules.matching_engine.api.slack.schemas import DealChoiceValue
from app.modules.matching_engine.api.slack.views.existing_deal_prompt import (
    build_existing_deal_prompt_blocks,
)
from app.modules.matching_engine.api.slack.views.full_analysis import build_full_analysis_blocks
from app.modules.matching_engine.api.slack.views.match_result import (
    build_match_result_blocks_from_view,
)
from app.modules.matching_engine.application.approvals import (
    InvalidTransitionError,
    MatchNotFoundError,
)
from app.modules.matching_engine.application.errors import (
    ExistingDealsFoundError,
    PartialWriteError,
)
from app.modules.matching_engine.domain.matching.deals import DealResolution
from app.modules.matching_engine.persistence.database import get_sessionmaker
from app.modules.notifications import SlackInteractionBody, SlackViewSubmissionPayload
from app.modules.utilities import get_shared_idempotency_store, get_shared_task_runner

logger = logging.getLogger(__name__)

_task_runner = get_shared_task_runner()
_submission_idempotency_store = get_shared_idempotency_store()


def register(app: AsyncApp) -> None:
    @app.view("buyer_selection_modal")
    async def handle_buyer_selection_submission(
        ack: AsyncAck, body: SlackInteractionBody, view: SlackViewSubmissionPayload
    ) -> None:
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
        requested_by = metadata.get("requested_by") or body["user"]["id"]
        channel_id = metadata.get("channel_id")
        if not channel_id:
            return

        values = view["state"]["values"]
        selected = values["buyer_role_id"]["selected_buyer"]["selected_option"]
        buyer_role_id = selected["value"]
        context_input = values.get("advisor_context", {}).get("context_text")
        advisor_context = (context_input.get("value") or "").strip() if context_input else ""

        _task_runner.run(
            lambda: run_match_and_post(
                buyer_role_id, requested_by, channel_id, advisor_context=advisor_context or None
            ),
            name=f"find-match:{buyer_role_id}",
        )

    @app.action("view_full_analysis")
    async def handle_view_full_analysis(
        ack: AsyncAck, body: SlackInteractionBody, client: AsyncWebClient
    ) -> None:
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

        # The session backs buyer_repository/meeting_repository only —
        # get_match_analysis never touches either — so it's closed right
        # after construction rather than held open across the call.
        async with get_sessionmaker()() as session:
            service = matching_engine_service(session)
        analysis = await service.get_match_analysis(run_id)
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
    async def handle_approve_match(
        ack: AsyncAck, body: SlackInteractionBody, client: AsyncWebClient, respond: AsyncRespond
    ) -> None:
        await ack()
        await _handle_decision(body, client, respond, decision="approve")

    @app.action("reject_match")
    async def handle_reject_match(
        ack: AsyncAck, body: SlackInteractionBody, client: AsyncWebClient, respond: AsyncRespond
    ) -> None:
        await ack()
        await _handle_decision(body, client, respond, decision="reject")

    @app.action(re.compile(r"promote_existing_deal_\d+|create_new_deal"))
    async def handle_deal_choice(
        ack: AsyncAck, body: SlackInteractionBody, client: AsyncWebClient, respond: AsyncRespond
    ) -> None:
        await ack()
        try:
            choice = DealChoiceValue.model_validate_json(body["actions"][0].get("value") or "")
        except ValidationError:
            await client.chat_postEphemeral(
                channel=body["channel"]["id"],
                user=body["user"]["id"],
                text="Invalid deal choice.",
            )
            return
        await _handle_decision(
            body,
            client,
            respond,
            decision="approve",
            match_result_id=choice.match_result_id,
            resolution=choice.resolution,
            existing_deal_id=choice.existing_deal_id,
            original_ts=choice.message_ts,
        )

    @app.action("cancel_deal_choice")
    async def handle_cancel_deal_choice(ack: AsyncAck, respond: AsyncRespond) -> None:
        await ack()
        await respond(delete_original=True)

    @app.action("discover_more_sellers")
    async def handle_discover_more_sellers(ack: AsyncAck, body: SlackInteractionBody) -> None:
        await ack()
        run_id_raw = body["actions"][0].get("value")
        channel_id = body["channel"]["id"]
        try:
            run_id = uuid.UUID(run_id_raw)
        except (ValueError, TypeError):
            return
        _task_runner.run(
            lambda: trigger_seller_discovery(run_id, channel_id=channel_id),
            name=f"discover:{run_id}",
        )

    @app.action("discrepancy_run_match")
    async def handle_discrepancy_run_match(ack: AsyncAck, body: SlackInteractionBody) -> None:
        await ack()
        buyer_role_id = body["actions"][0].get("value")
        channel_id = body["channel"]["id"]
        message_ts = body["message"]["ts"]
        requested_by = body["user"]["id"]
        if not buyer_role_id:
            return

        # Deduped on the message, not the buyer — a double click or a
        # retried Slack delivery of the same click must never run the match
        # twice against the same discrepancy-report message.
        idempotency_key = f"discrepancy_run:{channel_id}:{message_ts}"
        if _submission_idempotency_store.seen(idempotency_key):
            logger.info(
                "discrepancy_run_duplicate_delivery_skipped key=%s",
                idempotency_key,
                extra={"key": idempotency_key},
            )
            return
        _submission_idempotency_store.mark(idempotency_key)

        _task_runner.run(
            # The report already ran once for this message — explicitly
            # opts out rather than relying on a default, so the gate stays
            # on by default for every other caller.
            lambda: run_match_and_post(
                buyer_role_id,
                requested_by,
                channel_id,
                placeholder_ts=message_ts,
                check_discrepancies=False,
            ),
            name=f"find-match:{buyer_role_id}",
        )

    @app.action("discrepancy_cancel")
    async def handle_discrepancy_cancel(
        ack: AsyncAck, body: SlackInteractionBody, client: AsyncWebClient
    ) -> None:
        await ack()
        await client.chat_update(
            channel=body["channel"]["id"], ts=body["message"]["ts"], text="Match cancelled."
        )


def _partial_write_message(exc: PartialWriteError) -> str:
    if not exc.landed:
        return f"*Couldn't write the deal to Attio* — nothing was saved. _{exc.cause}_"
    return (
        "*Approval failed partway through.* Already saved: "
        f"{'; '.join(exc.landed)}. Check the match's status before retrying. _{exc.cause}_"
    )


async def _handle_decision(
    body: SlackInteractionBody,
    client: AsyncWebClient,
    respond: AsyncRespond,
    decision: str,
    *,
    match_result_id: uuid.UUID | None = None,
    resolution: DealResolution | None = None,
    existing_deal_id: str | None = None,
    original_ts: str | None = None,
) -> None:
    channel_id = body["channel"]["id"]
    user_id = body["user"]["id"]

    if match_result_id is None:
        try:
            match_result_id = uuid.UUID(body["actions"][0].get("value"))
        except (ValueError, TypeError):
            await client.chat_postEphemeral(
                channel=channel_id, user=user_id, text="Invalid match reference."
            )
            return

    # The session backs buyer_repository/meeting_repository only —
    # approve_match/reject_match/get_match_run_view never touch either (they
    # use their own short-lived uow_factory transactions) — so it's closed
    # right after construction rather than held open across this hot path.
    async with get_sessionmaker()() as session:
        service = matching_engine_service(session)

    try:
        result = (
            await service.approve_match(
                match_result_id,
                user_id,
                resolution=resolution,
                existing_deal_id=existing_deal_id,
            )
            if decision == "approve"
            else await service.reject_match(match_result_id, user_id)
        )
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
    except ExistingDealsFoundError as exc:
        await client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text="Attio already has a deal for this buyer and seller.",
            blocks=build_existing_deal_prompt_blocks(
                match_result_id, exc.deals, body.get("message", {}).get("ts")
            ),
        )
        return
    except PartialWriteError as exc:
        await client.chat_postEphemeral(
            channel=channel_id, user=user_id, text=_partial_write_message(exc)
        )
        return

    # Confirm the decision before rebuilding the view — the decision is
    # already committed at this point, so the operator must see this even
    # if the view rebuild below raises.
    await client.chat_postEphemeral(
        channel=channel_id,
        user=user_id,
        text=f"Match with {result.seller_org_name} {result.status.lower()} by <@{user_id}>.",
    )

    # Update the original message in place so a decided candidate's buttons
    # stop looking clickable (§23 — a repeat action must not appear possible).
    view = await service.get_match_run_view(uuid.UUID(result.run_id))
    if view is None:
        return
    text = f"Match results for {view.buyer_org_name}"
    blocks = build_match_result_blocks_from_view(view)
    if original_ts is None:
        await respond(replace_original=True, text=text, blocks=blocks)
        return
    # Coming from the ephemeral deal prompt: `respond` would overwrite the
    # prompt, so refresh the real message and drop the prompt.
    await client.chat_update(channel=channel_id, ts=original_ts, text=text, blocks=blocks)
    await respond(delete_original=True)
