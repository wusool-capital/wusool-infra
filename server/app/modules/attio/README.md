# attio

The Attio CRM vendor integration — API client, webhook envelope types, and
value-extraction/serialization helpers. `ddl_commands` is this module's one
real consumer today; extracted into its own peer module for organizational
clarity (Attio is a large, self-contained integration surface), not because
a second consumer exists yet. No `persistence/`, no `api/`, no
`bootstrap.py` — this module owns no tables and no HTTP surface of its own.

Treated as a **full-access peer module**, the same documented exception
`utilities` gets: `ddl_commands` imports directly from
`app.modules.attio.providers.attio.*`/`app.modules.attio.domain.*` for the
specific vendor helpers it needs (date/money serialization, signature
verification, retry, registry lookups), not just `AttioClientProtocol`.

## Structure

_New to this codebase's layering? See [the modular monolith guide](../../../../docs/dev/MODULAR_MONOLITH_GUIDE.md)._

```
attio/
  __init__.py                          # __all__: AttioClient, AttioClientProtocol, AttioError,
                                          # WebhookEvent, WebhookEventId, get_attio_client
  config.py                            # independent Settings.attio_api_key
  application/ports/client.py          # AttioClientProtocol
  domain/
    webhook.py                            # WebhookEvent, WebhookEventId dataclasses
    records.py                            # AttioRecord/AttioValueEntry TypedDicts — the generic
                                            # record/list-entry envelope shape, confirmed against docs
  providers/attio/
    values.py                            # value-extraction helpers (vals, ref, money, date, ...) —
                                            # vendor-payload parsing, not a framework-free primitive
    client.py                            # AttioClient, get_attio_client() — HTTP client + auth
    dates.py, money.py, options.py        # payload (de)serialization helpers
    signature.py                         # verify_attio_signature — webhook signature check
    registry.py                          # object/list id -> api_slug lookups
    retry.py                             # retry policy for the webhook-sync path only
    entries.py                           # create/patch organization + list-entry helpers
```

## Public contract

`__all__`: `AttioClient`, `AttioClientProtocol`, `AttioError`,
`WebhookEvent`, `WebhookEventId`, `get_attio_client`. Beyond that, callers
reach into `providers.attio.*`/`domain.*` directly (the full-access
exception above) rather than everything being funneled through
`AttioClientProtocol`.

Independent `config.py`: reads the same `ATTIO_API_KEY` env var
`ddl_commands`'s own `Settings` also reads, but through its own
`pydantic-settings` class — avoids an import-time cycle back to
`ddl_commands.config`.

`ddl_commands/providers/attio/write_payload.py` (Slack-form field values →
Attio write shape, coupled to `ddl_commands`'s own `FieldSpec`) and
`ddl_commands/persistence/attio_sync.py` (writes `ddl_commands`'s own
`organizations`/`buyer_roles`/`seller_roles` tables from Attio data) are
**not** part of this module — both are genuinely `ddl_commands`-owned
business logic that happens to call into this module's vendor helpers.

## Where to go next

New to this module? See [`HOW-TO-READ.md`](HOW-TO-READ.md).
