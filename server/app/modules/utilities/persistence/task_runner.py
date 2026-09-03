"""Concrete `TaskRunner` implementation."""

import asyncio
import logging

from app.modules.utilities.application.ports.task_runner import CoroFactory, TaskRunner

__all__ = ["TaskRunner", "InProcessTaskRunner"]

logger = logging.getLogger(__name__)


class InProcessTaskRunner:
    """Wraps `asyncio.create_task`. Keeps a reference to each task (asyncio
    only holds a weak reference internally, which can let a task vanish
    mid-flight) and logs any exception via a done-callback instead of
    letting it disappear silently.
    """

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[None]] = set()

    def run(self, coro_factory: CoroFactory, *, name: str) -> None:
        task = asyncio.create_task(coro_factory(), name=name)
        self._tasks.add(task)
        task.add_done_callback(self._on_done)

    def _on_done(self, task: asyncio.Task[None]) -> None:
        self._tasks.discard(task)
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error(
                "background_task_failed", extra={"task_name": task.get_name()}, exc_info=exc
            )
