"""The one entry point `matching_engine`'s "Find more sellers" button calls
into — search, render, post, all in one call so the caller only ever needs
an industry/geography/channel/exclude_terms, never anything about how
discovery works internally. `exclude_terms` is opaque here — just strings a
found lead's category/name is filtered against, with no notion of where
they came from (a buyer's `sector_exclusion` requirement, on the caller's
side). Exported via this module's root `__all__`.
"""

import logging

from app.modules.discovery.api.dependencies import discovery_service
from app.modules.discovery.config import get_settings
from app.modules.notifications import SlackWebClientNotifier, get_slack_client

logger = logging.getLogger(__name__)


async def find_and_post_leads(
    *, industry: str, geography: str, channel_id: str, exclude_terms: tuple[str, ...] = ()
) -> None:
    from app.modules.discovery.api.slack.views import build_lead_blocks

    settings = get_settings()
    notifier = SlackWebClientNotifier(get_slack_client(settings.slack_bot_token))
    placeholder_ts = await notifier.post_message(
        channel=channel_id, text="🔎 *_Searching for potential sellers…_*"
    )
    try:
        leads = await discovery_service().find_leads(
            industry=industry,
            geography=geography,
            limit=settings.discovery_lead_search_limit,
            exclude_terms=exclude_terms,
        )
    except Exception:
        logger.exception("discovery_lead_search_failed", extra={"industry": industry})
        await notifier.update_message(
            channel=channel_id, ts=placeholder_ts, text="Seller search failed unexpectedly."
        )
        return

    await notifier.update_message(
        channel=channel_id,
        ts=placeholder_ts,
        text=f"Found {len(leads)} potential seller(s)",
        blocks=build_lead_blocks(leads),
    )
