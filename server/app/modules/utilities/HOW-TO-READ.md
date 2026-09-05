# How to read `utilities`

A walkthrough for someone who has never seen this module before. If
you've read any other module's `HOW-TO-READ.md` first, you've already
seen half of this one by reference — `AppError`, `retry_with_backoff`,
`get_engine`/`get_sessionmaker`, `TaskRunner` all come from here. This
file ties those together.

## The one-sentence version

Cross-cutting infrastructure every other module depends on — logging,
base exceptions, retry, `Money`, database engine/session wiring,
idempotency, and background-task running. It has no business rules of
its own; it's a toolbox, not a bounded context.

## Why it's shaped like a "real" module even though it isn't one

`utilities` follows the same `domain/`/`application/`/`persistence/`/
`api/` layout as every module that DOES own a business concept, purely
for consistency — there's no `organizations`-style "why isn't there a
domain layer" question here, because there genuinely is a `domain/`
(errors, `Money`, retry, logging), it just happens to hold generic
primitives instead of business rules.

It's also a **full-access peer module**, the same documented exception
`attio` gets: other modules import its `persistence/`/`api/` submodules
directly, not just a narrow Port. That's why you'll see, e.g.,
`matching_engine`'s `bootstrap.py` importing
`app.modules.utilities.persistence.engine` directly instead of going
through some `DatabasePort`.

## The pieces, grouped by what they're for

### Errors — `domain/errors.py`

`AppError` (base, `status_code = 500`), `NotFoundError` (404),
`ValidationFailedError` (422). Every module's own domain-facing
exceptions subclass one of these instead of raising a bare
`HTTPException` — that's what keeps `domain/`/`application/` code
independent of FastAPI: raise an `AppError` subclass from anywhere, and
`api/handlers.py`'s `register_exception_handlers` (see below) turns it
into the right HTTP response automatically, with zero FastAPI import at
the raise site.

### Retry — `domain/retry.py`

`retry_with_backoff` factors out ONLY the retry-loop mechanic (try, check
if retryable, sleep, try again) — every actual policy decision (how many
attempts, how long to wait, which errors are worth retrying) is supplied
by the caller as arguments, since those genuinely differ per vendor
(Bedrock's transient-error codes aren't Attio's rate-limit convention).
If you're adding retry logic to a new provider client, use this instead
of writing another `for attempt in range(...)` loop — several modules
already did before this existed, and keeping the loop mechanic in one
place is the whole point.

### Money — `domain/money.py`

One `Money` frozen dataclass (`amount`, `currency`) shared by every
column that stores the same JSONB money shape. Deliberately a plain
dataclass, not a Pydantic model, so it stays usable from `domain/` code
that must stay framework-free — Pydantic v2 still validates it correctly
when it shows up as a field inside an actual `pydantic.BaseModel` at the
API layer, so this costs nothing on the API-schema side. Also has
`parse_usd_amount`, a strict `"USD <amount>[K|M|B]"` parser used where a
human types a monetary requirement as free text.

### Logging — `domain/logging.py`

`configure_logging(log_level)` sets up one JSON-lines log formatter for
the whole process. Two things worth knowing if you're debugging logs or
adding a new module:

- **Every log line gets tagged with a `service` field**, derived from the
  logger name's third path segment (`app.modules.<this>.*`) via a small
  hardcoded `_SERVICE_BY_MODULE` dict. If a module's logs are showing up
  tagged `"other"` instead of that module's name, this dict is why —
  it needs an entry added for a new module, it isn't automatic.
- **`log_context`** is a `contextvars.ContextVar` any handler can
  `.set()` request-scoped fields into (Slack trigger, user id, ...) —
  every log line emitted while that context is active picks those fields
  up automatically, without threading them through every function call.

### Database wiring — `persistence/{engine,health,registry,schema_check}.py`

`get_engine(database_url)`/`get_sessionmaker(database_url)` are
`lru_cache`d by URL — call them with the same URL from two different
modules and you get the SAME engine/connection pool back, not two
redundant ones. Every module's own `persistence/database.py` wraps these
with that module's own settings baked in, so callers everywhere still
write the familiar no-arg `get_engine()`.

`check_database_connectivity` backs every module's `/readiness` endpoint
(`SELECT 1`, nothing else). `import_all_models` makes sure every ORM
model is imported so cross-module relationship string references (like
`Organization.buyer_roles: Mapped[list["BuyerRole"]]`) can actually
resolve — every module's `bootstrap.py`/test setup calls this once.
`find_schema_drift` is test-time-only tooling that compares the live
database against what the ORM models expect — it never modifies
anything, and it's deliberately not run at app startup (that would
reintroduce a hard database dependency the app is designed to boot
without).

### Idempotency and background tasks — the two `Port` + concrete pairs

Both follow the same shape: `application/ports/{idempotency,task_runner}.py`
declares a `Protocol`, `persistence/{idempotency,task_runner}.py` has the
one real implementation.

- **`IdempotencyStore`** — a plain dict-with-TTL
  (`InMemoryIdempotencyStore`). Exists because Slack can redeliver the
  same command/action twice (its own retry, or a network blip), and
  nothing should silently re-run an expensive workflow because of a
  duplicate delivery.
- **`TaskRunner`** — wraps `asyncio.create_task` (`InProcessTaskRunner`),
  but keeps a strong reference to every task it starts (a bare
  `asyncio.create_task` call only holds a weak reference internally,
  which can let a task silently vanish mid-flight) and logs any exception
  a background task raises instead of letting it disappear. This is the
  seam between "a Slack handler needs to ack fast and do the real work
  after" and "how that work actually gets scheduled" — swappable for a
  real queue later without touching any Slack handler.

### `api/handlers.py` — the one FastAPI-dependent file

`register_exception_handlers(app)` is the only place in this module that
imports `fastapi`, which is exactly why it's deliberately **not** in the
module's `__all__` (see `README.md`'s "Public contract") — importing
anything else from `utilities` must never transitively pull `fastapi`
into a `domain/`-only consumer. A `bootstrap.py` that needs it (already
importing FastAPI itself, by definition) reaches in directly via
`app.modules.utilities.api.handlers`.

## Where to go next

- Adding retry to a new provider client → `domain/retry.py`'s
  `retry_with_backoff`, not a hand-rolled loop.
- A new module's logs showing up tagged `"other"` →
  `domain/logging.py`'s `_SERVICE_BY_MODULE`.
- Wiring a new module's database access → look at how an existing
  module's own `persistence/database.py` wraps `persistence/engine.py`.
- "How do I make a Slack handler ack fast and do slow work after?" →
  `TaskRunner`/`InProcessTaskRunner`.
