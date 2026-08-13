"""In-process background task dispatch, kept behind a Protocol so a durable
queue/worker can replace it later without touching any use case (§3, §28).
"""

from app.shared.tasks.runner import InProcessTaskRunner, TaskRunner

__all__ = ["InProcessTaskRunner", "TaskRunner"]
