# ddl-commands

`/edit-seller`, `/edit-buyer` — editing buyer/seller profiles (and, for
fields the operator picks, their organization) directly in DEV Attio, then
`wusool_crm` Postgres. `/add-seller`, `/add-buyer` — the same Attio-first
principle extended to creates: search for an existing organization first,
attach the new role to it if there's no role of that kind yet, or create a
brand new organization if nothing matched.

**Not independently deployed.** This is one of two folders that make up a
single Slack bot — see `../README.md` for how this fits together with
`../matching-engine/` and how the bot actually runs (`../main.py`, one
process, one Slack app). This folder's own `ddl_commands/main.py` still
exists and works (its own test suite uses it), but it is not the deployed
entrypoint.

`/remove-seller`/`/remove-buyer` don't exist — built and then deliberately
removed, see "History" below.

## The edit flow

1. `/edit-seller <name>` / `/edit-buyer <name>` — fuzzy search, disambiguation
   modal (same pg_trgm pattern `/find-match` uses).
2. **Field picker** — a modal listing every editable field, grouped
   "Organization" and "Seller/Buyer profile" (checkboxes, both optional —
   pick whichever you actually came to change). See
   `ddl_commands/modules/{sellers,buyers}/field_spec.py` and
   `ddl_commands/shared/organization_field_spec.py` for the authoritative
   eligibility list — not every DB column is offered; see "Excluded fields"
   below.
3. **Edit form** — only the fields picked in step 2, pre-filled with current
   values.
4. **Submit** — writes to **DEV Attio first**, then Postgres, in the same
   request. If the Attio write fails, nothing is written to Postgres at
   all. See "Why Attio-first" below.

## The add flow

1. `/add-seller <org name>` / `/add-buyer <org name>` — fuzzy search against
   `organizations` directly (not role-scoped, unlike the edit flow's
   search). No match → straight to step 3 with a blank organization.
2. **Organization selection** — shown only when the search found at least
   one candidate: attach the new role to one of them, or "None of these —
   create new organization". Picking an org that turns out to already have
   the target role (re-checked fresh, never trusted from the payload) stops
   here with a message pointing at `/edit-seller`/`/edit-buyer` instead.
3. **Add form** — *every* eligible field at once (not a field-picker like
   edit's step 2 — a creation moment is "fill in what I know now", not "pick
   one thing to change"), all optional except the organization's `name`
   (only shown, and required, when creating a new organization).
4. **Submit** — writes to **DEV Attio first**: create the organization
   record (only if new), then create the seller/buyer list entry FK'd to
   it; only then Postgres, in one transaction. If any Attio write fails,
   nothing is written to Postgres. If the org-create succeeds but the
   role-entry-create then fails, the org is *not* rolled back — it's simply
   there for the next `/add-*` attempt to find via search and attach to,
   which is why search-first matters (see "Why Attio-first" below).

## Why Attio-first, not a Postgres-only write

`database/sync-postgres.ps1` runs on its own schedule and does a full-column
`UPSERT` from Attio into `seller_roles`/`buyer_roles`/`organizations` — every
business field, every row, every run. A Slack-originated Postgres write with
no further protection would get silently overwritten by the next sync
cycle. Writing to Attio *first* means the sync's source of truth already
agrees with what Postgres is about to store — the next sync converges to
the same value instead of clobbering it. This needs **no new Postgres
columns** (an earlier version of this bot added `bot_managed_at`/
`bot_managed_by` guard columns without the data engineer's sign-off — that
was reverted; see "History" below).

## Excluded fields

Not every column on `organizations`/`seller_roles`/`buyer_roles` is
writable from Slack — the same eligibility list applies to both the edit
flow and the add flow's form, since both read from the same
`field_spec.py`/`organization_field_spec.py`:

- **`organizations.connection_strength`** — Attio-system-managed
  (recalculated from interaction history), never writable regardless of
  what the API permits.
- **`seller_roles.readiness_band`** — zero options currently defined in DEV
  Attio; nothing to show in a dropdown. Revisit once the data engineer adds
  options.
- **`readiness_score`, `lead_quality_score`, `acquisition_enrichment`,
  `deals_introduced`, `deals_converted`** — ownership is "both manual and
  pipeline-written" per the data engineer; editing these from Slack risks
  the same silent-overwrite problem this whole design exists to avoid, just
  from a different source. Needs explicit confirmation before inclusion.
- **`seller_roles.intake_source`** — included, but gated behind a required
  "this is a correction" checkbox on the edit form, matching its documented
  `write_once_except_correction` mutability.
- **`buyer_roles.key_contact`**, **`organizations.owner`** — reference types
  (a Person/Actor), not plain fields; deferred.
- Multi-select org fields other than `sector_focus` (`type`, `stage_focus`,
  `geographic_focus`, `domains`, `categories`) and `last_interaction_at` —
  deferred, not built this pass.

## Running this folder standalone (for isolated dev/testing only)

```bash
cd workflows/wusool-toolkit/ddl-commands
uv sync
cp .env.example .env  # then fill in real values, including ATTIO_API_KEY
uv run uvicorn ddl_commands.main:app --reload
```

- `GET /health` — liveness, no database dependency.
- `GET /readiness` (alias `GET /ready`) — confirms database connectivity.
- `POST /slack/events` — usable for isolated testing of this folder's own
  commands only; the deployed bot uses `../main.py` instead, which serves
  all 5 commands (this folder's 4 plus matching-engine's `/find-match`) off
  one Slack app.

## Testing

```bash
uv run pytest
```

DB-backed tests in `tests/integration/` skip cleanly when the database is
unreachable (no SSM tunnel open) rather than failing, and insert their own
throwaway org/role rows within a rolled-back transaction — nothing is ever
persisted, and this suite never needs to be run against real `wusool_crm`.
Attio-touching code (`ddl_commands/shared/attio/`) is unit-tested against a
mocked HTTP layer only — **nothing in this suite talks to real DEV Attio**;
whoever deploys this needs to smoke-test at least one real `/edit-seller`
and one real `/add-seller` against a real, low-stakes DEV org first — the
create path (`POST .../records`, `POST .../entries`) has never been
exercised against live Attio, only against the exact shapes
`workflows/crm-sync/scripts/_internal/{objects,lists}.ps1` already use live
(see `ddl_commands/shared/attio/entries.py`).

## Data model

Reads `organizations`, `buyer_roles`, `seller_roles` in the same
`wusool_crm` database matching-engine uses (`../../../database/README.md`
for the schema) and writes the same tables' business columns, after the
corresponding Attio write succeeds — inserting new rows (`/add-*`) as well
as updating existing ones (`/edit-*`). This bot never creates tables or
runs migrations, and never adds columns to any of them — schema changes are
the data engineer's call, not this bot's.

## History: the schema-authority correction

An earlier version of this bot added `database/sql/008_bot_managed_columns.sql`
(`removed_at`/`bot_managed_at`/`bot_managed_by` on `seller_roles`/
`buyer_roles`) and built `/remove-seller`/`/remove-buyer` on top of it,
without checking with the data engineer first. That was wrong — schema
changes aren't this bot's decision. Both were reverted: the migration file
is gone, matching-engine's own read-path filters that depended on it are
gone too, and `/remove-*` no longer exists. The sync-collision problem the
guard columns existed to solve is now handled by writing to Attio first
instead (see above) — a design that needs no schema changes at all.

## Out of scope (for now)

- `/remove-seller`, `/remove-buyer` — see "History" above.
- Any authorization/allowlist restricting who can run these commands.
- Horizontal scaling — the in-memory idempotency store is single-process
  only, same limitation matching-engine already has.
