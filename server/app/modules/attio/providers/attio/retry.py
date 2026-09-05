"""Retry wrapper for Attio API calls made from the webhook-driven sync path.

`AttioClient` itself deliberately has no retry logic (see its own module
docstring) — correct for a human-triggered Slack write, where a failure
should surface immediately rather than be silently retried. This path is
different: it's triggered by Attio's own webhook delivery, which can arrive
in bursts (a bulk edit fires one event per record, all at once), and
`sync-postgres.ps1` already established the right behavior for that shape of
traffic — retry on 429/5xx with backoff instead of dropping the event.
"""

import logging
from collections.abc import Awaitable, Callable

from app.modules.attio.application.ports.client import AttioClientProtocol
from app.modules.attio.providers.attio.client import AttioError
from app.modules.utilities.domain.retry import retry_with_backoff

_MAX_ATTEMPTS = 8

_logger = logging.getLogger("app.modules.attio.retry")


def _is_retryable(exc: Exception) -> bool:
    return isinstance(exc, AttioError) and (exc.status == 429 or exc.status >= 500)


def _delay_seconds(attempt: int) -> float:
    return min(90, 15 * attempt)


def _log_retry(attempt: int, exc: Exception, delay: float) -> None:
    # Logged, not silent: this backoff can spend up to 405s across its 8
    # attempts, and until now it did so without a word -- so a rate-limited
    # nightly resync was indistinguishable from a merely slow one when
    # reading the job output.
    status = exc.status if isinstance(exc, AttioError) else "?"
    _logger.warning(
        "attio %s — backing off %ds (attempt %d/%d)", status, delay, attempt, _MAX_ATTEMPTS
    )


async def _with_retry(call: Callable[[], Awaitable[dict]]) -> dict:
    return await retry_with_backoff(
        call,
        is_retryable=_is_retryable,
        max_attempts=_MAX_ATTEMPTS,
        delay_seconds=_delay_seconds,
        on_retry=_log_retry,
    )


async def get_with_retry(client: AttioClientProtocol, path: str) -> dict:
    return await _with_retry(lambda: client.get(path))


async def post_with_retry(client: AttioClientProtocol, path: str, json_body: dict) -> dict:
    return await _with_retry(lambda: client.post(path, json_body))


async def patch_with_retry(client: AttioClientProtocol, path: str, json_body: dict) -> dict:
    return await _with_retry(lambda: client.patch(path, json_body))
