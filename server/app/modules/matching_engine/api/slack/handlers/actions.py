"""Buyer-selection modal submission, "View Full Analysis", and
Approve/Reject button actions (§4, §21-24). Thin adapters: parse the Slack
payload, validate the id format, call the application use case, translate
the result back into a Slack message. Every action re-validates against the
database — Slack payload state is never trusted on its own (§24).
"""

import asyncio
import json
import logging
import re
import time
import uuid
from dataclasses import replace

from pydantic import ValidationError
from slack_bolt.async_app import AsyncApp
from slack_bolt.context.ack.async_ack import AsyncAck
from slack_bolt.context.respond.async_respond import AsyncRespond
from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

from app.modules.enrichment import enrich_and_post
from app.modules.matching_engine.api.dependencies import (
    find_buyer_discrepancies,
    matching_engine_service,
    run_match_and_post,
    to_match_analysis_schema,
    trigger_seller_discovery,
)
from app.modules.matching_engine.api.slack.schemas import (
    DealChoiceValue,
    DiscrepancyGateMetadata,
    RunAnywayValue,
)
from app.modules.matching_engine.api.slack.views.discovered_candidates import (
    build_discovered_candidates_blocks,
)
from app.modules.matching_engine.api.slack.views.discrepancy_gate import (
    build_discrepancy_gate_modal,
)
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
from app.modules.notifications import (
    SlackInteractionBody,
    SlackViewSubmissionPayload,
)
from app.modules.utilities import get_shared_idempotency_store, get_shared_task_runner

logger = logging.getLogger(__name__)

_task_runner = get_shared_task_runner()
_submission_idempotency_store = get_shared_idempotency_store()


def register(app: AsyncApp) -> None:
    @app.view("buyer_selection_modal")
    async def handle_buyer_selection_submission(
        ack: AsyncAck,
        body: SlackInteractionBody,
        view: SlackViewSubmissionPayload,
        client: AsyncWebClient,
    ) -> None:
        view_id = view.get("id")
        idempotency_key = f"buyer_selection_submission:{view_id}" if view_id else None
        if idempotency_key and _submission_idempotency_store.seen(idempotency_key):
            await ack()
            logger.info(
                "buyer_selection_duplicate_delivery_skipped key=%s",
                idempotency_key,
                extra={"key": idempotency_key},
            )
            return

        try:
            metadata = json.loads(view.get("private_metadata") or "{}")
            values = view["state"]["values"]
            selected = values["buyer_role_id"]["selected_buyer"]["selected_option"]
            context_input = values.get("advisor_context", {}).get("context_text")
            advisor_context = (context_input.get("value") or "").strip() if context_input else ""
            gate = DiscrepancyGateMetadata(
                buyer_role_id=selected["value"],
                channel_id=metadata.get("channel_id"),
                requested_by=metadata.get("requested_by") or body["user"]["id"],
                advisor_context=advisor_context or None,
            )
        except (KeyError, TypeError, ValueError):
            # Ack anyway: an un-acked submission shows Slack's connection error.
            logger.warning("buyer_selection_invalid_submission view_id=%s", view_id, exc_info=True)
            await ack()
            return

        # Marked only once parsing succeeds, so a failed submission can be retried.
        if idempotency_key:
            _submission_idempotency_store.mark(idempotency_key)
        # The popup opens with "Run anyway" already live, so it is never stuck if
        # the background update below lands before this one.
        await ack(
            response_action="update",
            view=build_discrepancy_gate_modal(gate, _CHECKING_TEXT),
        )
        if view_id:
            _task_runner.run(
                lambda: _show_discrepancies(client, view_id, gate),
                name=f"find-match-check:{gate.buyer_role_id}",
            )

    @app.view("discrepancy_gate_modal")
    async def handle_discrepancy_gate_submission(
        ack: AsyncAck, view: SlackViewSubmissionPayload
    ) -> None:
        await ack()

        view_id = view.get("id")
        if view_id:
            idempotency_key = f"discrepancy_gate_submission:{view_id}"
            if _submission_idempotency_store.seen(idempotency_key):
                logger.info(
                    "discrepancy_gate_duplicate_delivery_skipped key=%s",
                    idempotency_key,
                    extra={"key": idempotency_key},
                )
                return
            _submission_idempotency_store.mark(idempotency_key)

        try:
            gate = DiscrepancyGateMetadata.model_validate_json(view.get("private_metadata") or "")
        except ValidationError:
            logger.warning("discrepancy_gate_invalid_metadata view_id=%s", view_id)
            return

        _task_runner.run(
            lambda: run_match_and_post(
                gate.buyer_role_id,
                gate.requested_by,
                gate.channel_id,
                advisor_context=gate.advisor_context,
            ),
            name=f"find-match:{gate.buyer_role_id}",
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
        raw_value = body["actions"][0].get("value")
        channel_id = body["channel"]["id"]
        message_ts = body["message"]["ts"]
        requested_by = body["user"]["id"]
        if not raw_value:
            return
        try:
            run_value = RunAnywayValue.model_validate_json(raw_value)
        except ValidationError:
            # A button posted before the value carried context holds a bare id.
            run_value = RunAnywayValue(buyer_role_id=raw_value)
        buyer_role_id = run_value.buyer_role_id

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
            # Buttons on gate messages posted before the popup existed.
            lambda: run_match_and_post(
                buyer_role_id,
                requested_by,
                channel_id,
                advisor_context=run_value.advisor_context,
                placeholder_ts=message_ts,
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


_CHECKING_TEXT = ":hourglass_flowing_sand: _Checking the buyer's profile…_"
_CLEAR_TEXT = "No missing or conflicting details found for this buyer."
_FINDINGS_FALLBACK_TEXT = "This buyer's profile has missing or conflicting details."
_BUYER_GONE_TEXT = "This buyer could not be found. It may have been removed."
_CHECK_FAILED_TEXT = (
    ":warning: Couldn't check this buyer's profile, so missing or conflicting "
    "details may not be shown."
)
# ponytail: fixed delay, since Slack gives no signal for when the ack's view is applied.
_MIN_UPDATE_DELAY_S = 1.5


async def _show_discrepancies(
    client: AsyncWebClient, view_id: str, gate: DiscrepancyGateMetadata
) -> None:
    """Fills the popup with the check result. Never runs the match — only
    "Run anyway" does."""
    started = time.monotonic()
    try:
        result = await find_buyer_discrepancies(gate.buyer_role_id, gate.advisor_context)
    except Exception:
        logger.exception("discrepancy_check_failed", extra={"buyer_role_id": gate.buyer_role_id})
        text = _CHECK_FAILED_TEXT
    else:
        if result is None:
            text = _BUYER_GONE_TEXT
        elif result.report.is_clear:
            text = _CLEAR_TEXT
        else:
            text = result.message.strip() or _FINDINGS_FALLBACK_TEXT

    # A fast check could otherwise land before the ack's "Checking…" view and be overwritten.
    await asyncio.sleep(max(0.0, _MIN_UPDATE_DELAY_S - (time.monotonic() - started)))
    try:
        await client.views_update(view_id=view_id, view=build_discrepancy_gate_modal(gate, text))
    except SlackApiError as exc:
        if exc.response.get("error") == "not_found":
            # Closed, or already submitted via "Run anyway" — nothing left to show.
            logger.info("discrepancy_gate_modal_gone view_id=%s", view_id)
        else:
            logger.warning("discrepancy_gate_update_failed view_id=%s", view_id, exc_info=True)


def _partial_write_message(exc: PartialWriteError) -> str:
    if not exc.landed:
        return f"*Couldn't write the deal to Attio* — nothing was saved. _{exc.cause}_"
    return (
        "*Approval failed partway through.* Already saved: "
        f"{'; '.join(exc.landed)}. Check the match's status before retrying. _{exc.cause}_"
    )


def _enrich_approved_seller(seller_role_id: str | None, channel_id: str) -> None:
    """A discovered seller only got the basic (structured-provider) tier when it
    was created; once someone approves it, the full research proposal is worth
    the Firecrawl/LLM cost. It posts a proposal to review, never writes."""
    if seller_role_id is None:
        return
    _task_runner.run(
        lambda: enrich_and_post(kind="seller", role_id=seller_role_id, channel_id=channel_id),
        name=f"enrich-approved:{seller_role_id}",
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
        logger.error(
            "match_approval_partial_write match_result_id=%s landed=%s",
            match_result_id,
            exc.landed,
            exc_info=exc.cause,
            extra={"match_result_id": str(match_result_id), "landed": exc.landed},
        )
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
    # The CRM shortlist and discovered sellers are separate messages; refresh
    # only the one this decision came from.
    decided = next((r for r in view.results if r.match_result_id == result.match_result_id), None)
    if decision == "approve" and decided is not None and decided.origin == "discovery":
        _enrich_approved_seller(decided.seller_role_id, channel_id)
    if decided is not None and decided.origin == "discovery":
        text = f"Discovered sellers for {view.buyer_org_name}"
        blocks = build_discovered_candidates_blocks(
            [r for r in view.results if r.origin == "discovery"]
        )
    else:
        text = f"Match results for {view.buyer_org_name}"
        blocks = build_match_result_blocks_from_view(
            replace(view, results=[r for r in view.results if r.origin == "crm"])
        )
    if original_ts is None:
        await respond(replace_original=True, text=text, blocks=blocks)
        return
    # Coming from the ephemeral deal prompt: `respond` would overwrite the
    # prompt, so refresh the real message and drop the prompt.
    await client.chat_update(channel=channel_id, ts=original_ts, text=text, blocks=blocks)
    await respond(delete_original=True)
