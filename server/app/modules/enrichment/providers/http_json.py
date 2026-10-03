"""Shared fail-soft "GET a JSON body" helper for the structured
company-data providers (Diffbot, People Data Labs) — the only two callers
in this codebase that talk to a vendor via raw `aiohttp` rather than an
SDK. Kept local to this package rather than in `utilities`, which has no
other `aiohttp` dependency today; if a third raw-`aiohttp` caller shows up
outside `enrichment`, that's the point to reconsider moving it.
"""

import asyncio
import logging

import aiohttp

from app.modules.utilities.domain.json_types import JsonObject

logger = logging.getLogger(__name__)


# One retry, and only when the vendor asks for a short wait — a longer
# Retry-After would stall a Slack-facing run past its own time budget.
_MAX_ATTEMPTS = 2
_MAX_RETRY_AFTER_S = 2.0


def _retry_delay(header: str | None) -> float | None:
    """`None` when the header is absent, an HTTP-date, or too long to wait on."""
    if header is None:
        return None
    try:
        delay = float(header)
    except ValueError:
        return None
    return delay if 0 <= delay <= _MAX_RETRY_AFTER_S else None


async def fetch_json(
    *,
    url: str,
    params: dict[str, str],
    timeout: aiohttp.ClientTimeout,
    log_prefix: str,
    org_name: str,
) -> JsonObject | None:
    """`None` on any failure — non-200 status, connection error, timeout, or
    a malformed body — logged as a warning, never raised. A 429 is logged as
    `{prefix}_rate_limited` (distinct from "no data found") and retried once
    when the vendor's `Retry-After` is short.
    """
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for attempt in range(_MAX_ATTEMPTS):
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    if resp.status != 429:
                        logger.warning(
                            "%s_failed org_name=%s status=%d", log_prefix, org_name, resp.status
                        )
                        return None
                    delay = _retry_delay(resp.headers.get("Retry-After"))
                    logger.warning(
                        "%s_rate_limited org_name=%s retry_after=%s attempt=%d",
                        log_prefix,
                        org_name,
                        delay,
                        attempt + 1,
                    )
                if delay is None or attempt + 1 == _MAX_ATTEMPTS:
                    return None
                await asyncio.sleep(delay)
    except Exception:
        logger.warning("%s_error org_name=%s", log_prefix, org_name, exc_info=True)
        return None
    return None
