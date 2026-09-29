"""Generic in-process fixed-window rate limiter. Framework-free (stdlib
`time` only) -- callers own their own key choice (per-IP, per-install-id,
...) and limit/window policy.

Previously duplicated near-verbatim in `lead_magnets/api/dependencies.py`
and `meetings/api/feedback.py`, each with its own comment explaining why
it couldn't import the other's copy (`lead_magnets/__init__.py` declares
no `__all__`, so nothing may import from it at all). Promoted here once a
second call site needed it, so a fix to the algorithm (e.g. adding
eviction) lands once instead of twice.
"""

import time


class FixedWindowRateLimiter:
    """Per-key fixed window, in process.

    One container per environment (dev/prod each run their own toolkit
    instance), so an in-process counter is accurate rather than merely
    convenient. Resets on deploy and does not survive a second instance --
    move it to Redis or a WAF rule only if either of those becomes true.
    """

    def __init__(self, *, limit: int, window_s: int = 3600) -> None:
        self._limit = limit
        self._window_s = window_s
        self._hits: dict[str, tuple[float, int]] = {}

    def check(self, key: str, *, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        started, count = self._hits.get(key, (now, 0))
        if now - started >= self._window_s:
            started, count = now, 0
        if count >= self._limit:
            return False
        self._hits[key] = (started, count + 1)
        return True

    def refund(self, key: str) -> None:
        """Gives back one hit, for work that was counted but never happened
        (e.g. the upstream call failed before doing anything)."""
        entry = self._hits.get(key)
        if entry is not None and entry[1] > 0:
            self._hits[key] = (entry[0], entry[1] - 1)
