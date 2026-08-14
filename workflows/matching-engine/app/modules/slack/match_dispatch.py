"""Shared background-task body for running the match pipeline and posting
its result to Slack — used by both the `/find-match` command handler and
the buyer-selection modal submission handler.
"""

import logging
import uuid

from app.config import get_settings
from app.modules.buyers.dependencies import resolve_buyer_by_id
from app.modules.matching.dependencies import (
    build_run_match_use_case,
    build_web_lead_search_service,
)
from app.modules.matching.domain.scoring import needs_web_fallback
from app.modules.slack.views.match_result import build_match_result_blocks
from app.modules.slack.views.web_fallback import build_web_fallback_blocks

logger = logging.getLogger(__name__)


async def run_match_and_post(buyer_role_id: str, requested_by: str, channel_id: str) -> None:
    # Local import: `bolt_app` -> `handlers` -> `actions`/`commands` ->
    # this module, so a top-level import here would be circular.
    from app.modules.slack.bolt_app import get_bolt_app

    app = get_bolt_app()
    placeholder = await app.client.chat_postMessage(
        channel=channel_id, text="🔍 Finding matches, please wait…"
    )

    buyer = await resolve_buyer_by_id(buyer_role_id)
    if buyer is None:
        await app.client.chat_update(
            channel=channel_id,
            ts=placeholder["ts"],
            text="Buyer not found.",
        )
        return

    result = await build_run_match_use_case().execute(buyer, requested_by=requested_by)

    blocks = build_match_result_blocks(result)
    scores = [c.match_score for c in result.results]
    if result.status == "GENERATED" and needs_web_fallback(
        scores, get_settings().web_fallback_min_score
    ):
        lead_search = build_web_lead_search_service()
        leads = await lead_search.search(uuid.UUID(result.run_id)) if lead_search else []
        logger.info(
            "web_fallback_triggered run_id=%s leads_found=%d",
            result.run_id,
            len(leads),
            extra={"run_id": result.run_id, "leads_found": len(leads)},
        )
        if leads:
            blocks = build_web_fallback_blocks(result.buyer_org_name, leads)

    await app.client.chat_update(
        channel=channel_id,
        ts=placeholder["ts"],
        text=f"Match results for {result.buyer_org_name}",
        blocks=blocks,
    )
