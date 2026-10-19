"""Shared fail-soft "send a request, get a JSON body" helpers for the
structured company-data providers (Diffbot, People Data Labs) and the Apify
LinkedIn source — the only callers in this codebase that talk to a vendor
via raw `aiohttp` rather than an SDK. Kept local to this package rather than
in `utilities`, which has no other `aiohttp` dependency today; if a caller
shows up outside `enrichment`, that's the point to reconsider moving it.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

import aiohttp
from pydantic import BaseModel, ValidationError

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


async def _request[T](
    *,
    method: str,
    url: str,
    params: dict[str, str],
    headers: dict[str, str] | None,
    body: str | None,
    ok_statuses: frozenset[int],
    read: Callable[[aiohttp.ClientResponse], Awaitable[T]],
    timeout: aiohttp.ClientTimeout,
    log_prefix: str,
    org_name: str,
) -> T | None:
    # A POST can start a billed vendor run, so it is never resent after a 429.
    max_attempts = _MAX_ATTEMPTS if method == "GET" else 1
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for attempt in range(max_attempts):
                if method == "POST":
                    request = session.post(url, params=params, headers=headers, data=body)
                else:
                    request = session.get(url, params=params, headers=headers)
                async with request as resp:
                    if resp.status in ok_statuses:
                        return await read(resp)
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
                if delay is None or attempt + 1 == max_attempts:
                    return None
                await asyncio.sleep(delay)
    except Exception:
        logger.warning("%s_error org_name=%s", log_prefix, org_name, exc_info=True)
        return None
    return None


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
    return await _request(
        method="GET",
        url=url,
        params=params,
        headers=None,
        body=None,
        ok_statuses=frozenset({200}),
        read=lambda resp: resp.json(),
        timeout=timeout,
        log_prefix=log_prefix,
        org_name=org_name,
    )


async def post_json_items[M: BaseModel](
    *,
    url: str,
    params: dict[str, str],
    headers: dict[str, str],
    body: str,
    item_type: type[M],
    timeout: aiohttp.ClientTimeout,
    log_prefix: str,
    org_name: str,
) -> list[M] | None:
    """POSTs a JSON `body` and returns the array the vendor answers with,
    parsed into `item_type`s — Apify's run-sync dataset endpoint answers 201,
    not 200. An item that doesn't parse is dropped and logged; the raw JSON
    never leaves this function. `None` on any failure, including a body that
    isn't an array; same logging and 429 handling as `fetch_json`.
    """
    parsed = await _request(
        method="POST",
        url=url,
        params=params,
        headers={**headers, "Content-Type": "application/json"},
        body=body,
        ok_statuses=frozenset({200, 201}),
        read=lambda resp: resp.json(),
        timeout=timeout,
        log_prefix=log_prefix,
        org_name=org_name,
    )
    if parsed is None:
        return None
    if not isinstance(parsed, list):
        logger.warning("%s_unexpected_body org_name=%s", log_prefix, org_name)
        return None
    items: list[M] = []
    for raw in parsed:
        try:
            items.append(item_type.model_validate(raw))
        except ValidationError:
            logger.warning("%s_item_unparseable org_name=%s", log_prefix, org_name)
    return items
