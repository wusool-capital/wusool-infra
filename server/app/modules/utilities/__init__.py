"""Cross-cutting infrastructure shared by every other module — logging,
base exceptions, retry, `Money`, DB engine/session wiring, idempotency,
background-task running. Not a bounded context (no business rules of its
own), but kept in the same domain/application/persistence/api shape as
every other module for consistency.

Public cross-module facade — see the module-boundary rule in
`server/tests/test_architecture.py`: other modules may only import names
listed in `__all__` here. Deliberately excludes `register_exception_handlers`
(`api/handlers.py`, `fastapi`-dependent) — importing it via this root
`__init__.py` would pull `fastapi` into every consumer's import graph, even a
`domain/` file that only wants `Money`. A `bootstrap.py`-level consumer (which
already imports `fastapi` itself) reaches it directly via
`app.modules.utilities.api.handlers` instead.
"""

from app.modules.utilities.application.ports.idempotency import IdempotencyStore
from app.modules.utilities.application.ports.task_runner import TaskRunner
from app.modules.utilities.domain.errors import AppError, NotFoundError, ValidationFailedError
from app.modules.utilities.domain.logging import configure_logging, log_context
from app.modules.utilities.domain.money import Money, parse_usd_amount
from app.modules.utilities.domain.retry import retry_with_backoff
from app.modules.utilities.persistence.engine import get_engine, get_sessionmaker
from app.modules.utilities.persistence.health import check_database_connectivity
from app.modules.utilities.persistence.idempotency import InMemoryIdempotencyStore
from app.modules.utilities.persistence.registry import import_all_models
from app.modules.utilities.persistence.schema_check import find_schema_drift
from app.modules.utilities.persistence.task_runner import InProcessTaskRunner

__all__ = [
    "AppError",
    "IdempotencyStore",
    "InMemoryIdempotencyStore",
    "InProcessTaskRunner",
    "Money",
    "NotFoundError",
    "TaskRunner",
    "ValidationFailedError",
    "check_database_connectivity",
    "configure_logging",
    "find_schema_drift",
    "get_engine",
    "get_sessionmaker",
    "import_all_models",
    "log_context",
    "parse_usd_amount",
    "retry_with_backoff",
]
