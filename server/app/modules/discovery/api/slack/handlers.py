"""Registers `discover_add_seller` on the shared Bolt app — the button is
emitted for leads that fuzzy-matched an existing CRM organization and so were
not auto-created (see `build_possible_duplicate_blocks`). The coupling to
`matching_engine`, which posts that message, is a shared action_id/value
contract, not a Python import.

Clicking it hands the lead to `ddl_commands`' `/add-seller` flow through
`SellerDraftPort.open_confirm_form`: its organization search is the human's
final duplicate check before anything is written.
"""

import logging

from slack_bolt.async_app import AsyncApp
from slack_bolt.context.ack.async_ack import AsyncAck
from slack_sdk.web.async_client import AsyncWebClient

from app.modules.discovery.api.dependencies import decode_lead, discovery_service
from app.modules.discovery.domain.drafts import draft_from_lead
from app.modules.notifications import SlackInteractionBody

logger = logging.getLogger(__name__)


def register_handlers(app: AsyncApp) -> None:
    @app.action("discover_add_seller")
    async def handle_discover_add_seller(
        ack: AsyncAck, body: SlackInteractionBody, client: AsyncWebClient
    ) -> None:
        await ack()
        action = body["actions"][0]
        channel_id = body["channel"]["id"]
        user_id = body["user"]["id"]
        trigger_id = body["trigger_id"]

        try:
            lead = decode_lead(action["value"])
        except Exception:
            # A stale/legacy button value (e.g. after a deploy changes
            # `DiscoveredLead`'s shape) must not fail silently after `ack()`
            # has already fired — the operator needs to see *something*.
            logger.exception("discover_lead_decode_failed")
            await client.chat_postEphemeral(
                channel=channel_id, user=user_id, text="Couldn't process that lead."
            )
            return

        try:
            await discovery_service().open_confirm_form(
                trigger_id=trigger_id,
                draft=draft_from_lead(lead),
                channel_id=channel_id,
                requested_by=user_id,
            )
        except Exception:
            logger.exception("discover_confirm_form_failed", extra={"lead_name": lead.name})
            await client.chat_postEphemeral(
                channel=channel_id, user=user_id, text=f"Couldn't process *{lead.name}*."
            )
