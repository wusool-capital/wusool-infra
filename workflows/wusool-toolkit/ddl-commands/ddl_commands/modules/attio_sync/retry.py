"""Retry wrapper for Attio API calls made from the webhook-driven sync path.

`AttioClient` itself deliberately has no retry logic (see its own module
docstring) — correct for a human-triggered Slack write, where a failure
should surface immediately rather than be silently retried. This path is
different: it's triggered by Attio's own webhook delivery, which can arrive
in bursts (a bulk edit fires one event per record, all at once), and
`sync-postgres.ps1` already established the right behavior for that shape of
traffic — retry on 429/5xx with backoff instead of dropping the event.
"""

import asyncio

from ddl_commands.shared.attio.client import AttioClient, AttioError

_MAX_ATTEMPTS = 8


async def _with_retry(call):
    for attempt in range(_MAX_ATTEMPTS):
        try:
            return await call()
        except AttioError as exc:
            if exc.status != 429 and exc.status < 500:
                raise
            if attempt == _MAX_ATTEMPTS - 1:
                raise
            await asyncio.sleep(min(90, 15 * (attempt + 1)))
    raise AssertionError("unreachable")  # pragma: no cover


async def get_with_retry(client: AttioClient, path: str) -> dict:
    return await _with_retry(lambda: client.get(path))


async def post_with_retry(client: AttioClient, path: str, json_body: dict) -> dict:
    return await _with_retry(lambda: client.post(path, json_body))


async def patch_with_retry(client: AttioClient, path: str, json_body: dict) -> dict:
    return await _with_retry(lambda: client.patch(path, json_body))
