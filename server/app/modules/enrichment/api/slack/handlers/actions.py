"""Role-selection modal submission, and the "Review & Save" button from the
proposal message. That button carries an opaque, server-generated token
(never operator-editable Slack input) resolved back to the real proposal by
`decode_proposal` — see `proposal_store.py` for why it's a token and not the
proposal itself — and opens `ddl_commands`' real edit form for review; this
module never writes anything itself.
"""

import json
import logging

from slack_bolt.async_app import AsyncApp
from slack_bolt.context.ack.async_ack import AsyncAck
from slack_sdk.web.async_client import AsyncWebClient

from app.modules.enrichment.api.dependencies import propose_and_post, target_from_resolved
from app.modules.enrichment.api.slack.views.proposal_message import decode_proposal
from app.modules.notifications import SlackInteractionBody, SlackViewSubmissionPayload
from app.modules.utilities import (
    NotFoundError,
    get_shared_idempotency_store,
    get_shared_task_runner,
)

logger = logging.getLogger(__name__)

_task_runner = get_shared_task_runner()
_submission_idempotency_store = get_shared_idempotency_store()


def register(app: AsyncApp) -> None:
    @app.view("enrichment_role_selection_modal")
    async def handle_role_selection_submission(
        ack: AsyncAck,
        body: SlackInteractionBody,
        view: SlackViewSubmissionPayload,
        client: AsyncWebClient,
    ) -> None:
        await ack()

        view_id = view.get("id")
        if view_id:
            idempotency_key = f"role_selection_submission:{view_id}"
            if _submission_idempotency_store.seen(idempotency_key):
                logger.info("role_selection_duplicate_delivery_skipped key=%s", idempotency_key)
                return
            _submission_idempotency_store.mark(idempotency_key)

        metadata = json.loads(view.get("private_metadata") or "{}")
        channel_id = metadata.get("channel_id")
        if not channel_id:
            # No channel to post to even if we wanted to — this modal's own
            # `private_metadata` should always carry one, so this is an
            # internal-invariant violation, not a normal user-facing case.
            logger.warning("role_selection_submission_missing_channel_id")
            return

        selected = view["state"]["values"]["role_id"]["selected_role"]["selected_option"]["value"]
        kind, role_id = selected.split(":", 1)

        # `propose_and_post` needs the org name/id too, which this modal's
        # options only carried as the visible label — re-resolve fresh
        # rather than parse the label back apart.
        from app.modules.enrichment.api.dependencies import resolve_org_roles

        search_term = metadata.get("search_term", "")
        candidates = await resolve_org_roles(search_term) if search_term else []
        match = next((c for c in candidates if c.role_id == role_id and c.kind == kind), None)
        if match is None:
            # The candidate set changed between the modal being built and
            # submitted (a role deactivated, an org renamed) — without this,
            # the operator sees the modal close with no result and no
            # indication anything went wrong.
            await client.chat_postEphemeral(
                channel=channel_id,
                user=metadata.get("requested_by") or body["user"]["id"],
                text="That selection is no longer available — run `/enrich-seller` or "
                "`/enrich-buyer` again.",
            )
            return
        _task_runner.run(
            lambda: propose_and_post(target_from_resolved(match), channel_id=channel_id),
            name=f"enrich:{role_id}",
        )

    @app.action("enrichment_review")
    async def handle_review(
        ack: AsyncAck, body: SlackInteractionBody, client: AsyncWebClient
    ) -> None:
        await ack()
        action = body["actions"][0]
        channel_id = body["channel"]["id"]
        user_id = body["user"]["id"]
        trigger_id = body["trigger_id"]

        from app.modules.enrichment.api.dependencies import enrichment_service

        try:
            proposal = decode_proposal(action["value"])
        except NotFoundError:
            # The proposal store's TTL expired, or the process restarted
            # since it was posted — the button itself is otherwise fine,
            # there's just nothing left to resolve it to.
            await client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text="This proposal has expired — run `/enrich-seller` or "
                "`/enrich-buyer` again to regenerate it.",
            )
            return

        try:
            await enrichment_service().open_review_form(
                trigger_id=trigger_id,
                proposal=proposal,
                channel_id=channel_id,
                requested_by=user_id,
            )
        except Exception:
            logger.exception(
                "enrichment_review_form_failed", extra={"org_name": proposal.target.org_name}
            )
            await client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=f"Couldn't open the review form for *{proposal.target.org_name}*.",
            )
