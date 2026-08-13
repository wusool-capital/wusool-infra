"""§3: the Slack command handler must ack immediately and never block on
Bedrock/DB work. `TaskRunner` is the seam between "dispatch the workflow"
and "how it actually runs" — swappable for a durable queue later without
changing any use case or Slack handler.
"""

import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any, Protocol

logger = logging.getLogger(__name__)

_CoroFactory = Callable[[], Coroutine[Any, Any, None]]


class TaskRunner(Protocol):
    def run(self, coro_factory: _CoroFactory, *, name: str) -> None: ...


class InProcessTaskRunner:
    """Wraps `asyncio.create_task`. Keeps a reference to each task (asyncio
    only holds a weak reference internally, which can let a task vanish
    mid-flight) and logs any exception via a done-callback instead of
    letting it disappear silently.
    """

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task] = set()

    def run(self, coro_factory: _CoroFactory, *, name: str) -> None:
        task = asyncio.create_task(coro_factory(), name=name)
        self._tasks.add(task)
        task.add_done_callback(self._on_done)

    def _on_done(self, task: asyncio.Task) -> None:
        self._tasks.discard(task)
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error(
                "background_task_failed", extra={"task_name": task.get_name()}, exc_info=exc
            )
