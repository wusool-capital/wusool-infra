"""Shared fail-soft "GET a JSON body" helper for the structured
company-data providers (Diffbot, People Data Labs) — the only two callers
in this codebase that talk to a vendor via raw `aiohttp` rather than an
SDK. Kept local to this package rather than in `utilities`, which has no
other `aiohttp` dependency today; if a third raw-`aiohttp` caller shows up
outside `enrichment`, that's the point to reconsider moving it.
"""

import logging

import aiohttp

from app.modules.utilities.domain.json_types import JsonObject

logger = logging.getLogger(__name__)


async def fetch_json(
    *,
    url: str,
    params: dict[str, str],
    timeout: aiohttp.ClientTimeout,
    log_prefix: str,
    org_name: str,
) -> JsonObject | None:
    """`None` on any failure — non-200 status, connection error, timeout, or
    a malformed body — logged as a warning, never raised. Every caller
    already treats "no answer" and "provider down" identically, so this is
    the one place that distinction gets collapsed rather than at each
    call site.
    """
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    logger.warning(
                        "%s_failed org_name=%s status=%d", log_prefix, org_name, resp.status
                    )
                    return None
                return await resp.json()
    except Exception:
        logger.warning("%s_error org_name=%s", log_prefix, org_name, exc_info=True)
        return None
