"""§28: Slack can retry a slash command/action delivery (its own retry
mechanism, or a network blip on our side). Don't accidentally re-run an
expensive workflow because of a duplicate delivery.
"""

from typing import Protocol


class IdempotencyStore(Protocol):
    def seen(self, key: str) -> bool: ...
    def mark(self, key: str) -> None: ...
