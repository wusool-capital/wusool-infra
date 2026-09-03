# utilities

Cross-cutting infrastructure shared by every other module: logging,
base exceptions, retry-with-backoff, `Money`, DB engine/session wiring,
idempotency, in-process background-task running. Not a bounded context (no
business rules of its own) — kept in the same domain/application/
persistence/api shape as every other module for consistency, and treated
as a **full-access peer module**: other modules import its `persistence/`/
`api/`/`domain/` submodules directly rather than only its Port surface, the
same documented exception `attio` gets.

## Structure

_New to this codebase's layering? See [the modular monolith guide](../../../../docs/dev/MODULAR_MONOLITH_GUIDE.md)._

```
utilities/
  __init__.py                  # __all__ facade — deliberately excludes register_exception_handlers
                                  # (fastapi-dependent) to avoid pulling fastapi into domain/ consumers
  domain/
    errors.py                    # AppError, NotFoundError, ValidationFailedError
    money.py                       # Money — plain frozen dataclass, not pydantic (domain-purity)
    retry.py                         # retry_with_backoff
    logging.py                         # configure_logging, log_context
  application/ports/
    idempotency.py                 # IdempotencyStore Protocol
    task_runner.py                   # TaskRunner Protocol
  persistence/
    engine.py                    # get_engine(url) / get_sessionmaker(url) — lru_cached per URL
    health.py                      # check_database_connectivity(engine)
    registry.py                      # import_all_models()
    schema_check.py                    # find_schema_drift()
    idempotency.py                       # InMemoryIdempotencyStore (concrete)
    task_runner.py                         # InProcessTaskRunner (concrete)
  api/handlers.py               # register_exception_handlers — the one fastapi-dependent piece
```

## Public contract

`__all__`: `AppError`, `NotFoundError`, `ValidationFailedError`, `Money`,
`parse_usd_amount`, `retry_with_backoff`, `configure_logging`,
`log_context`, `IdempotencyStore`, `InMemoryIdempotencyStore`, `TaskRunner`,
`InProcessTaskRunner`, `check_database_connectivity`, `find_schema_drift`,
`get_engine`, `get_sessionmaker`, `import_all_models`.

`register_exception_handlers` is deliberately **not** in `__all__` — a
`bootstrap.py`-level consumer (which already imports `fastapi` itself)
reaches it via `app.modules.utilities.api.handlers` directly instead of the
root facade, so importing anything else from this module never transitively
pulls in `fastapi`.

Each consuming module's `persistence/database.py` wraps `engine.py`/
`health.py`/`registry.py` with that module's own `get_settings().database_url`
baked in, keeping every existing caller's no-arg
`get_engine()`/`get_sessionmaker()`/`check_database_connectivity()` call
signature unchanged.

## Testing

`tests/test_architecture.py` enforces this module's own `domain/`/
`application/` never import its own `persistence/`/`api/`/`fastapi`/
`pydantic`/`sqlalchemy` directly — unaffected by other modules' full-access
exception to reach into `persistence/`/`api/` themselves.
