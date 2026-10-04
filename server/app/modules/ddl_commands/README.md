# ddl_commands

`/edit-seller`, `/edit-buyer` — edit buyer/seller profiles (and, for fields
the operator picks, their organization) in SOURCE Attio first, then
`wusool_crm` Postgres. `/add-seller`, `/add-buyer` — the same Attio-first
principle for creates: search for an existing organization first, attach
the new role to it, or create a brand new organization if nothing matched.

`/remove-seller`/`/remove-buyer` don't exist — built and then deliberately
reverted (see "History" below).

Not independently deployed — `server/main.py` merges this module's Slack
handlers with `matching_engine`'s onto one `AsyncApp`. `bootstrap.py::create_app()`
here exists only for running this module standalone (its own test suite).

## Structure

_New to this codebase's layering? See [the modular monolith guide](../../../../docs/internal/dev/MODULAR_MONOLITH_GUIDE.md)._

```
ddl_commands/
  bootstrap.py       # composition root — build_* factories, standalone create_app()
  config.py          # Settings (pydantic-settings)
  application/       # base.py (ServiceBase) + buyers.py/sellers.py (BuyerService/
                       # SellerService mixins) + service.py (DdlCommandsService facade,
                       # composes both by multiple inheritance) + application/ports/
                       # Protocols. No domain/ layer — every consumer works with
                       # app.models ORM rows directly. attio_sync.py's webhook
                       # dispatcher stays outside the facade — a stateless per-event
                       # dispatcher, not a service with dependencies injected once.
  persistence/       # SQLAlchemy repositories, Unit-of-Work, attio_sync writeback
  providers/attio/   # write_payload.py — this module's own field-to-Attio-payload mapping
                       # (the vendor client/helpers themselves live in app.modules.attio)
  api/                # router.py (aggregates health.py + attio_sync.py's routers),
                       # Slack handlers, dependencies.py
  scripts/            # attio_sync_full_resync.py — standalone nightly batch job
  tests/
```

Organization persistence (search, CRUD) lives in the `app.modules.organizations`
peer module, shared with `matching_engine`. Attio's vendor client, webhook
types, and value-extraction helpers live in the `app.modules.attio` peer
module — this module reaches into `attio.providers`/`attio.domain` directly
(a documented full-access exception, same as `utilities`) for anything
beyond the `AttioClientProtocol` Port.

## The edit flow

1. `/edit-seller <name>` / `/edit-buyer <name>` — fuzzy search, disambiguation
   modal (one option per organization for buyers).
   1a. **Buyers only — vertical step** (`buyer_vertical_selection.py`): a buyer
   holds one role per vertical, so the operator picks an existing role to edit
   or an unused vertical to create. An organization with no buyer role at all
   gets a pointer to `/add-buyer` instead. Picking an unused vertical here
   goes to the add form, exactly as in the add flow below.
2. **Field picker** — a modal listing every editable field, grouped
   "Organization" and "Seller/Buyer profile" (see `api/schemas.py`'s
   `FieldSpec`/`FieldKind` and `api/organizations.py`'s `ORGANIZATION_FIELDS`
   for the authoritative eligibility list — not every column is offered, see
   "Excluded fields" below).
3. **Edit form** — only the fields picked in step 2, pre-filled with current
   values.
4. **Submit** — writes to **SOURCE Attio first**, then Postgres, in the same
   request. If the Attio write fails before anything landed, nothing is
   written to Postgres. If a partial write already landed (e.g. org fields
   in Attio before a role-field write failed), the ephemeral message names
   exactly what already landed (`PartialWriteError` in
   `api/slack/handlers/actions.py`).

## The add flow

1. `/add-seller <org name>` / `/add-buyer <org name>` — fuzzy search against
   `organizations` directly. No match → straight to step 3 with a blank org.
2. **Organization selection** — shown only if the search found candidates:
   attach the new role to one, or create a new organization. For sellers,
   picking an org that already has the role (re-checked fresh) stops here
   with a pointer to `/edit-seller` instead.
   2a. **Buyers only — vertical step** (`buyer_vertical_selection.py`): shown
   for every buyer add, including a brand-new organization. An organization
   holds one active buyer role per vertical, so picking an existing role
   routes into the edit flow's field picker, and picking an unused vertical
   opens the add form with the vertical fixed. `target_vertical` is chosen
   here only — the add form and field picker leave it out, so a role can't be
   moved onto a vertical another role already holds.
3. **Add form** — every eligible field at once, all optional except a new
   organization's `name`. If similar orgs were found and the user still
   picks "create new", the form warns about the duplicate but doesn't block.
4. **Submit** — for a buyer on an existing organization, Postgres is first
   checked for an active role in the same vertical, before anything reaches
   Attio: Attio's newest-wins reconcile would demote the existing role if a
   duplicate entry landed there. Then writes to **SOURCE Attio first**
   (organization, if new, then the role entry), then Postgres in one
   transaction. If the role-entry
   write fails after the org-create succeeded, the org is *not* rolled
   back — the next `/add-*` attempt finds it via search.

### Headless seller add (discovery)

`api/seller_write.py::write_seller_add` is the Attio-first seller write the
`/add-seller` submission calls, kept out of the Slack handler so
`providers/discovery/seller_writer_adapter.py` can call it too. It returns the
created `SellerRole` and raises `PartialWriteError` (`api/write_errors.py`) with
what already landed. The adapter also runs the CRM pre-filter lookup and basic
enrichment, returns the lead unwritten as `UnverifiedSeller` when a provider's
website doesn't match the Maps website (see `discovery/README.md`), then
writes once. A reviewed lead's `source_place_id` travels through the
organization-selection and add-form `private_metadata` to the same write. `source_place_id` goes to Postgres only: Attio has
no such attribute, and the sync's `COALESCE` keeps it.

## Why Attio-first, not a Postgres-only write

`scripts/postgres-sync/prod/sync-source-to-prod.ps1` runs on its own schedule and
does a full-column UPSERT from Attio into `seller_roles`/`buyer_roles`/
`organizations`. A Slack-originated Postgres write with no further
protection would get silently overwritten by the next sync cycle. Writing
to Attio first means the sync's source of truth already agrees with what
Postgres is about to store — the next sync converges instead of clobbering.

## Deletions: Attio is the only place a record can be deleted

Postgres is a mirror of Attio for six tables — `organizations`, `person`,
`deals`, `notes`, `buyer_roles`, `seller_roles`. A record deleted in Attio
must disappear from Postgres too, and the mirror runs **one way only**: there
is no Postgres-originated delete, no `/remove-*` command, and
`AttioClientProtocol` has no `delete` verb at all. Deleting Postgres-first
would be worse than useless — the nightly resync re-reads Attio and
resurrects the row.

The mirror is a **soft delete**. Each of the six tables carries a
Postgres-only `removed_at timestamptz` (no Attio attribute corresponds to
it). `record.deleted` / `list-entry.deleted` stamps it via
`persistence/attio_sync.py`'s `delete_*` functions, dispatched from
`application/attio_sync.py`'s `_RECORD_DELETE_METHODS` /
`_LIST_DELETE_METHODS`; every upsert resets it to `NULL`, so a record
re-created in Attio comes back live rather than staying flagged. Consumers
must therefore filter `removed_at IS NULL`.

Soft rather than hard delete because a `DELETE` here destroys data Attio
cannot rebuild: `deals` cascades into `deal_stage_events` and `documents`,
both role tables cascade into `match_results`, and
`notes.{buyer,seller}_role_id` / `tool_runs.{buyer,seller}_role_id` declare
no `ON DELETE` at all — so deleting a referenced role raises a foreign-key
violation instead. The `ON DELETE CASCADE` clauses are left in place
deliberately: with nothing hard-deleting these rows they are unreachable.

Two keys differ from the sync path's usual `attio_id`: `notes` is keyed on
`id` (which holds the Attio record id verbatim for Attio-originated notes),
and the role deletes are keyed on **`legacy_entry_id`**, because
`list-entry.deleted` reports the list entry and that id is the only
Attio-derived identity those rows have.

## Excluded fields

Not every column on `organizations`/`seller_roles`/`buyer_roles` is
writable from Slack (same eligibility list for both edit and add):

- `organizations.connection_strength` — Attio-system-managed, never writable.
- `seller_roles.readiness_band` — was unwritable while its Attio select had
  zero options; the four (Early, Developing, Sale Ready, Market Ready) were
  added 2026-09-07, so this is now only a Slack-form gap.
- `readiness_score`, `lead_quality_score`, `acquisition_enrichment`,
  `deals_introduced`, `deals_converted` — both manual- and pipeline-written;
  editing from Slack risks the same silent-overwrite problem this design
  exists to avoid. Needs explicit sign-off before inclusion.
- `seller_roles.intake_source` — included, gated behind a "this is a
  correction" checkbox on the edit form.
- `buyer_roles.key_contact`, `organizations.owner` — genuine editable
  fields, excluded only because both are reference types (Person/User) and
  no search-and-select UI exists for those yet — not a policy question.
- Multi-select org fields other than `sector_focus`, and
  `last_interaction_at` — deferred, not built.

## Setup

Config comes from the repo-root `server/.env` (see `.env.example` there).
Relevant variables: `DATABASE_URL`, `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`,
`ATTIO_API_KEY`, `ATTIO_WEBHOOK_SECRET`, and `ATTIO_IS_TEST` — which half of the single shared SOURCE workspace this
instance owns. `true` (the default) stamps every record it creates
`is_test = true`, refuses to edit production records, and ignores inbound
Attio webhooks entirely; `false` is the inverse. In the deployed
environments it is templated from Terraform's `var.environment`.

## Running standalone (dev/testing only)

```bash
uv run uvicorn --factory app.modules.ddl_commands.bootstrap:create_app --reload
```

- `GET /health`, `GET /readiness` (alias `/ready`), `POST /slack/events` —
  same shape as `matching_engine`'s. `POST /webhooks/attio` — inbound Attio
  webhook sync, signature-verified.

## Testing

```bash
uv run pytest
```

DB-backed integration tests insert their own throwaway rows inside a
rolled-back transaction — nothing is ever persisted, and the suite never
needs a real `wusool_crm`. Attio-touching code is unit-tested against a
mocked HTTP layer only — **nothing in this suite talks to real Attio**;
smoke-test at least one real `/edit-seller` and one real `/add-seller`
against a low-stakes DEV org before deploying a change to the create path.

## Where to go next

New to this module? See [`HOW-TO-READ.md`](HOW-TO-READ.md).

## History: the schema-authority correction

An earlier version of this bot added a `bot_managed_at`/`bot_managed_by`/
`removed_at` migration on `seller_roles`/`buyer_roles` and built
`/remove-seller`/`/remove-buyer` on top of it, without the data engineer's
sign-off. That was wrong — schema changes aren't this bot's call. Both were
reverted. The sync-collision problem those guard columns existed to solve
is now handled by writing to Attio first instead (see above).

`removed_at` has since come back to those two tables, and to `deals`/`notes`,
in migration `b8c41e7d09a2` — with sign-off, and for a different reason: it
mirrors a deletion **authored in Attio** (see "Deletions" above), not one
authored by this bot. `bot_managed_at`/`bot_managed_by` and the `/remove-*`
commands stay reverted, and nothing about that reversal is being
re-litigated.

## Known limitation: concurrent writes to the same organization

`DdlCommandsService.create_seller`/`create_buyer` re-check for an existing
*active* role immediately before the Postgres insert. That check used to be
backed by `UNIQUE(org_attio_id)` on `seller_roles`/`buyer_roles`; the
2026-08-28 migration (`b8f4c1e93a56`) moved that constraint to
`legacy_entry_id` so an org can hold one row per SOURCE Attio entry, which
left the check unbacked — two submissions could both pass it before either
committed and both write `is_active=true`.

It is now serialized by a row lock on the parent `organizations` row
(`OrganizationRepository.lock`), taken inside the same transaction before
the check: a second `/add-seller` for the same org blocks there and only
reads once the first has committed, so it sees the new role and raises
`SellerAlreadyExistsError`. Two things that deliberately does not do:

- It doesn't stop the losing submission from having already created a
  duplicate *Attio* entry, since the lock is taken after the Attio writes
  (see "Why Attio-first"). `_reconcile_active_entry` demotes that entry on
  the next sync — that's what `is_active` is for. Closing this too would
  mean holding the lock across the Attio round-trip: the per-org advisory
  lock discussed here previously, still not built.
- It's a use-case-level guarantee, not a DB constraint, so it doesn't
  constrain the webhook sync path or a future direct writer. A partial
  unique index (`org_attio_id` WHERE `is_active`, or `(org_attio_id,
  target_vertical)` for `buyer_role`, whose active grain is one role per
  vertical) would, but Postgres can't
  defer a partial unique index and `sync_buyer_role`/`sync_seller_role`
  promote an org's new winner before demoting the old one inside a single
  transaction — so that index would reject every duplicate-entry promotion
  unless those loops are reordered losers-first first. Note also the
  pre-existing duplicate `org_attio_id` rows in production, predating this
  bot: such an index would need a dedupe before it could be built.

## Out of scope (for now)

- `/remove-seller`, `/remove-buyer` — see "History" above.
- Any authorization/allowlist restricting who can run these commands.
- Horizontal scaling — the in-memory idempotency store is single-process
  only, same limitation `matching_engine` has.
