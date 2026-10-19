"""Runs one HarvestAPI actor synchronously and parses its dataset items —
the only place that knows Apify's run-sync endpoint, auth header and cost
log. Fails soft: any error yields an empty list.
"""

import logging
import time
from typing import TypeVar

import aiohttp
from pydantic import BaseModel, ValidationError

from app.modules.enrichment.providers.http_json import post_json_array

logger = logging.getLogger(__name__)

_RUN_SYNC_URL = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"
# Headroom over Apify's own run timeout so the vendor aborts (and stops
# billing) before our client gives up on the connection.
_HTTP_HEADROOM_S = 5

_Item = TypeVar("_Item", bound=BaseModel)


class ApifyClient:
    def __init__(self, token: str) -> None:
        self._token = token

    async def run(
        self,
        *,
        actor: str,
        actor_input: BaseModel,
        item_type: type[_Item],
        run_timeout_s: int,
    ) -> list[_Item]:
        started = time.monotonic()
        raw_items = await post_json_array(
            url=_RUN_SYNC_URL.format(actor=actor),
            params={"timeout": str(run_timeout_s)},
            headers={"Authorization": f"Bearer {self._token}"},
            body=actor_input.model_dump_json(),
            timeout=aiohttp.ClientTimeout(total=run_timeout_s + _HTTP_HEADROOM_S),
            log_prefix="apify_run",
            org_name=actor,
        )
        items: list[_Item] = []
        for raw in raw_items or []:
            try:
                items.append(item_type.model_validate(raw))
            except ValidationError:
                logger.warning("apify_item_unparseable actor=%s", actor)
        logger.info(
            "apify_run actor=%s items=%d duration_ms=%d outcome=%s",
            actor,
            len(items),
            int((time.monotonic() - started) * 1000),
            "ok" if raw_items is not None else "failed",
        )
        return items
