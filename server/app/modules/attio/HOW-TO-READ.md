# How to read `attio`

A walkthrough for someone who has never seen this module before. See
`README.md` for scope and public contract.

## The one-sentence version

This module is a **toolbox for talking to Attio's API**, not a service —
it has no database tables, no HTTP endpoints, and no `bootstrap.py`.
`ddl_commands` is the one real consumer today; it reaches into this
module's pieces directly rather than everything being funneled through
one narrow interface.

## Why this module looks different from the others

Every other module in `app/modules/` has `persistence/` and often `api/`
because it owns some piece of the product (a Slack command, a database
table). This one owns neither — it exists purely so the large, fiddly
"how do you correctly talk to Attio" logic lives in one place instead of
scattered across `ddl_commands`. If you're used to tracing one HTTP
request through a module (like `meetings`' `HOW-TO-READ.md` does), that
doesn't apply here — there's no request to trace. Instead, think of this
as three separate toolboxes, described below.

## The three jobs this module does

### 1. Make an HTTP call to Attio (`providers/attio/client.py`)

`AttioClient` is a thin `aiohttp` wrapper: `get`/`post`/`patch`, each
raising `AttioError` on any non-2xx response. Two things worth knowing:

- **It has no retry logic, on purpose.** Its own docstring explains why:
  most of its callers are a human-triggered Slack write happening inside
  one interaction — a failure there should surface immediately, not be
  silently retried and leave the user waiting.
- **`get_attio_client()`** is the process-wide singleton (one reused
  `aiohttp.ClientSession` for the app's whole lifetime — cheaper than
  opening a new connection per call). A short-lived caller that wants its
  own session instead can construct `AttioClient(api_key)` directly and
  use it as `async with AttioClient(...) as client:`.

### 2. Read Attio's write-shape correctly (`providers/attio/{values,dates,money,options}.py`)

Attio's API doesn't return plain JSON values — every attribute is wrapped
in a type-specific envelope (a select field's value lives at
`option.title`, a reference field's at `target_record_id`, and so on).
`values.py` is the whole "unwrap this correctly" toolbox: `first()`,
`ref()`, `titles()`, `money()`, `date()`/`timestamp()`, one function per
attribute shape. If you're reading a new field off an Attio record,
you almost certainly want one of these, not hand-rolled dict indexing.

`dates.py` and `money.py` exist because Attio's *write* shape has real
gotchas that look like they shouldn't matter but do:
- A `date` field (`"YYYY-MM-DD"`, no time) and a `timestamp` field (full
  ISO-8601) are genuinely different attribute types — writing the wrong
  shape to the wrong one fails. `serialize_date` picks the right one
  per-field, from a hardcoded field→type map.
- A `currency` field can only ever be written as `{"currency_value":
  <number>}` — including `currency_code` in the write body raises a 400.
  (Confirmed the hard way, per the file's own comment.) The currency
  itself is fixed in Attio's own workspace config, not settable per-write.

`options.py` looks up select-field option IDs live rather than
hardcoding them, because they're workspace-specific and drift.

### 3. Verify and process an inbound webhook (`providers/attio/{signature,registry,retry}.py`, `domain/webhook.py`)

This is the *other* direction — Attio calling *us*, not the other way
around. Three pieces:

- **`signature.py`** — `verify_attio_signature` checks the HMAC-SHA256
  signature Attio puts on every webhook delivery, using
  `hmac.compare_digest` (not `==`, to avoid a timing side-channel).
- **`registry.py`** — a webhook payload identifies its object/list by an
  opaque UUID, not the human-readable slug (`"organizations"`,
  `"buyer_role"`) the rest of the codebase uses. `object_slug()`/
  `list_slug()` translate one to the other, fetched once and cached.
- **`retry.py`** — unlike `AttioClient` itself, calls made *while
  processing* a webhook DO retry (up to 8 attempts, capped backoff).
  Why the asymmetry: a webhook can arrive in a burst (a bulk edit fires
  one event per record, all at once), so dropping one on a transient
  429/5xx is worse here than it would be for a single human-triggered
  Slack write.

`domain/webhook.py` (`WebhookEvent`/`WebhookEventId`) and
`domain/records.py` (`AttioRecord`/`AttioValueEntry`) are just the plain
dataclass/TypedDict shapes these three files hand data around in — no
logic, just types.

## The one thing worth remembering

**This module is deliberately a "full-access peer module"** — the
`README.md` explains the mechanics, but the reason is: Attio's API surface
is large and `ddl_commands` needs a lot of different pieces of it (date
serialization, signature checks, retry, registry lookups), not just "make
a request." Forcing all of that through one narrow
`AttioClientProtocol` would mean either a bloated protocol or a second,
parallel set of helper functions duplicating what's already here. So
`ddl_commands` reaches directly into `providers.attio.*`/`domain.*` — that
is the intended usage, not a shortcut someone took.

## Where to go next

- Reading a new attribute off an Attio record → `providers/attio/values.py`.
- Writing a new field to Attio → check `dates.py`/`money.py` first for a
  gotcha, then `entries.py` for how a write is actually issued.
- Working on the webhook-driven sync path → `registry.py` (id→slug),
  `retry.py` (why calls here retry when `AttioClient` itself doesn't),
  `domain/webhook.py` (the envelope shape).
- The actual sync business logic (writing Postgres from Attio data) is
  **not in this module** — see `ddl_commands/persistence/attio_sync.py`.
