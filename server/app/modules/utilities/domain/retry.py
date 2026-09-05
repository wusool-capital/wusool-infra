"""Generic bounded-retry-with-backoff loop. Callers own their own
attempt-count/delay/retryability policy — those legitimately differ per
vendor (rate-limit conventions, transient-error signatures) — this only
factors out the loop mechanic itself, previously reimplemented
independently per call site.
"""

import asyncio
from collections.abc import Awaitable, Callable


async def retry_with_backoff[T](
    call: Callable[[], Awaitable[T]],
    *,
    is_retryable: Callable[[Exception], bool],
    max_attempts: int,
    delay_seconds: Callable[[int], float],
    on_retry: Callable[[int, Exception, float], None] | None = None,
) -> T:
    """Calls `call()`, retrying up to `max_attempts` times total.

    `is_retryable(exc)` decides whether a given failure should be retried at
    all. `delay_seconds(attempt)` (1-indexed) returns how long to sleep
    before the next attempt. `on_retry(attempt, exc, delay)`, if given, runs
    right before each sleep — for a caller that wants to log the retry with
    its own vendor-specific detail (status code, error code, ...). Re-raises
    the last exception once attempts are exhausted or `is_retryable` returns
    `False`.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            return await call()
        except Exception as exc:
            if not is_retryable(exc) or attempt == max_attempts:
                raise
            delay = delay_seconds(attempt)
            if on_retry is not None:
                on_retry(attempt, exc, delay)
            await asyncio.sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover
