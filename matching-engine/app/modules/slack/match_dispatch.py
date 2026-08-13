"""Shared background-task body for running the match pipeline and posting
its result to Slack — used by both the `/find-match` command handler and
the buyer-selection modal submission handler.
"""

from app.modules.buyers.dependencies import resolve_buyer_by_id
from app.modules.matching.dependencies import build_run_match_use_case
from app.modules.slack.views.match_result import build_match_result_blocks


async def run_match_and_post(buyer_role_id: str, requested_by: str, channel_id: str) -> None:
    # Local import: `bolt_app` -> `handlers` -> `actions`/`commands` ->
    # this module, so a top-level import here would be circular.
    from app.modules.slack.bolt_app import get_bolt_app

    buyer = await resolve_buyer_by_id(buyer_role_id)
    if buyer is None:
        return

    result = await build_run_match_use_case().execute(buyer, requested_by=requested_by)

    app = get_bolt_app()
    await app.client.chat_postMessage(channel=channel_id, blocks=build_match_result_blocks(result))
