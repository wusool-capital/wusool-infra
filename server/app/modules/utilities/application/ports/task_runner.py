"""§3: a Slack command handler must ack immediately and never block on
slow work (Bedrock, DB, Attio). `TaskRunner` is the seam between "dispatch
the workflow" and "how it actually runs" — swappable for a durable queue
later without changing any use case or Slack handler.
"""

from collections.abc import Callable, Coroutine
from typing import Any, Protocol

CoroFactory = Callable[[], Coroutine[Any, Any, None]]


class TaskRunner(Protocol):
    def run(self, coro_factory: CoroFactory, *, name: str) -> None: ...
