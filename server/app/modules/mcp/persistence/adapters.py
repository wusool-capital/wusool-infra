"""v1 adapters: no tables. Correct for one server per environment (the toolkit
runs as a single instance); a restart forgets stored results."""

import time
from collections import OrderedDict
from collections.abc import Callable

from app.modules.mcp.domain.access import Caller, Permission

RESULT_TTL_SECONDS = 24 * 3600.0
_MAX_RESULTS = 5_000


class ActiveMemberPermissions:
    """Sign-in already limits callers to active, non-guest Slack members."""

    def allows(self, caller: Caller, permission: Permission) -> bool:
        return True


class InMemoryIdempotencyStore:
    def __init__(
        self,
        *,
        ttl_seconds: float = RESULT_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._entries: OrderedDict[str, tuple[float, str]] = OrderedDict()

    def get(self, key: str) -> str | None:
        entry = self._entries.get(key)
        if entry is None or entry[0] <= self._clock():
            self._entries.pop(key, None)
            return None
        return entry[1]

    def put(self, key: str, result: str) -> None:
        self._entries[key] = (self._clock() + self._ttl, result)
        self._entries.move_to_end(key)
        while len(self._entries) > _MAX_RESULTS:
            self._entries.popitem(last=False)
