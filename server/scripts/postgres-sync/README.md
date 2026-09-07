# SOURCE Attio to PostgreSQL

The `wusool_crm` PostgreSQL schema, and the transactional sync into it from
SOURCE Attio. Attio owns human-facing CRM state; PostgreSQL stores a
relational mirror plus automation, history, analytics, and AI data.

## One workspace, two environments

Since 2026-09-07 a single SOURCE Attio workspace serves both environments,
separated by an Attio-only `is_test` checkbox: `true` is dev/test, `false` is
production. There is no `is_test` PostgreSQL column — the split is applied as
a read-side filter here, at sync time.

**The sync runs SOURCE Attio -> the production database only.** Every fetch in
[`prod/`](prod) drops records flagged `is_test`.

## Dev is a sandbox, not a mirror

The dev database is deliberately **not** synced from Attio, and there is no
`dev/` script directory any more. A developer creates their own test data with
the Slack `/add-seller` / `/add-buyer` commands against the dev instance: each
writes to SOURCE Attio with `is_test = true` **and** to the dev database in the
same request (Attio first — see
[`ddl_commands/README.md`](../../app/modules/ddl_commands/README.md)), and
further `/edit-*` and `/find-match` commands then run against that org.

Two consequences worth knowing before you hit them:

- **A fresh dev database is empty.** `/find-match` has nothing to match
  against until someone has created a pool of buyer roles by hand. That is by
  design, not a bug.
- **Dev instances only see their own records.** The webhook route ignores
  inbound Attio deliveries entirely when `ATTIO_IS_TEST=true`, and an
  `/edit-*` against a production record is refused rather than executed.

If seeding ever becomes worth automating, the right shape is production
PostgreSQL -> dev PostgreSQL. Never a second Attio consumer.

## Command surface

All scripts live in [`prod/`](prod); see [`prod/README.md`](prod/README.md) for
the details and the order they run in.

| Script | Responsibility |
| --- | --- |
| `sync-all-to-prod.ps1` | The entry point: `sync-source-to-prod.ps1` then `sync-notes-from-source.ps1`, in that order. |
| `sync-source-to-prod.ps1` | Read SOURCE Attio's custom objects and role lists, drop `is_test` records, then dry-run or transactionally upsert. Reconciles: anything not fetched is removed. |
| `sync-notes-from-source.ps1` | Populates `notes` from SOURCE's `note` object. Pure upsert, no reconciliation pass. |
| `sync-meetings-from-source.ps1` | Meeting/interaction history. Runs on its own schedule, not part of the wrapper. |
| `validate-postgres.ps1` | Compare SOURCE/PostgreSQL counts and validate key relationships. Read-only, and `is_test`-aware so its counts agree with the sync's. |
| `backfill-activities.ps1` | One-off `activities` backfill. Reads SOURCE's *native* `companies`/`people`/`valuation_tool_leads`, which are the only place the boundary-interaction timestamps survive, and crosswalks them to V2 ids via `legacy_attio_id`. |

A nightly safety net also runs the server's own
`app.modules.ddl_commands.scripts.attio_sync_full_resync` against production —
see [`.github/workflows/nightly-attio-sync.yml`](../../../.github/workflows/nightly-attio-sync.yml).
It complements the real-time webhook (`POST /webhooks/attio`) rather than
replacing it.

### Mirroring every Attio record (2026-08-28)

`buyer_roles`/`seller_roles` used to be one row per organization
(`UNIQUE(org_attio_id)`), with the sync silently dropping every Attio list
entry except the active one before writing, specifically to keep that
constraint satisfiable. Per explicit product decision, Postgres
should mirror every Attio record that exists, full stop -- `is_active`
(already a column on both tables) is how a caller distinguishes the current
entry from stale duplicates, not something the sync script pre-filters on.

The unique constraint moved to `legacy_entry_id` (one row per SOURCE entry
instead of per org) via Alembic migration `b8f4c1e93a56`; `org_attio_id` is
now a plain indexed FK, so an org can have more than one `buyer_roles`/
`seller_roles` row. `Organization.buyer_role`/`.seller_role` became the
plural `buyer_roles`/`seller_roles` relationships in
`app/models/organization.py` to match. **Any consumer that assumed a
single buyer/seller role per organization must now filter to
`is_active=True` explicitly** -- this includes
`server/app/modules/matching_engine` and `.../ddl-commands` (Slack
`/edit-buyer`/`/edit-seller` and related), which have not been updated as
part of this change and should be checked before relying on this behavior
there.

## Prerequisites

- Python with `psycopg[binary]`.
- Active AWS SSM port-forwarding tunnel to private RDS.
- `DATABASE_URL` for `wusool_crm` through `localhost:15432`.
- `SOURCE_ATTIO_API_KEY` for synchronization.

See [`rds-tunnel-runbook.md`](rds-tunnel-runbook.md) for tunnel and credential
retrieval commands. Never share the RDS master password, complete admin
`DATABASE_URL`, AWS keys, or Attio keys.

## Schema changes now go through Alembic

The original `001`-`007` flat SQL files that first created this schema (and
the `setup-postgres.ps1` script that applied them) were deleted 2026-08-29 --
Alembic's baseline migrations (`d982478fc6e3` → `87320bb9dc8d` → `eec9dde1cfbb`)
fully reproduce what those files created, and every environment that matters
(`dev`, `prod`) already has its schema; see git history before this date if
you need the original files for reference.

The `server/` project is a Python package (`app/models/`, `pyproject.toml`)
holding the SQLAlchemy model for every table above, plus an
Alembic migration chain (`alembic.ini`, `alembic/`) that is now the source of
truth for **future** schema changes:

| Path | What it is |
| --- | --- |
| `app/models/` | One SQLAlchemy model per table, all registered on the one shared `Base` in `app/models/base.py`. Both `matching-engine` and `ddl-commands` import models from here — this is the *only* place any table is defined in Python. |
| `alembic/env.py` | Reads `DATABASE_URL` from the environment (the same secret the toolkit app itself already reads — never a new credential), imports every model so `--autogenerate` can see the full schema. |
| `alembic/versions/` | The actual migration files. `d982478fc6e3` → `87320bb9dc8d` → `eec9dde1cfbb` recreate everything `001`-`007` below produce, as the current baseline. |

### To make a schema change

1. Edit the relevant model(s) in `app/models/`. This is the single
   source of truth — `matching-engine` and `ddl-commands` only ever import
   models from here, never define their own.
2. From this directory: `uv sync --extra dev && uv run alembic revision
   --autogenerate -m "describe the change"`.
3. **Review the generated migration file before committing.** Autogenerate
   gets close but not everything — check it did what you expect, in
   particular:
   - **New native Postgres enum type?** Only use `create_type=False` on the
     column if you are hand-writing that type's `CREATE TYPE` in a migration
     yourself (this is what `meeting_source`/`counterparty_role`/
     `meeting_type` do, and why — see `d982478fc6e3`'s docstring). For a
     normal new enum, leave `create_type` at its default (`True`) and let
     autogenerate emit the `CREATE TYPE` for you. Setting `create_type=False`
     without a matching hand-written `CREATE TYPE` makes `alembic upgrade
     head` fail outright against an empty database — `ci.yml`'s
     `alembic-check` job will catch this on the PR, but the fix is to not
     copy that pattern unless you need it, not to debug the CI failure after
     the fact.
   - **Extensions, role grants, and non-default constraint names** —
     autogenerate does not manage `CREATE EXTENSION`, `GRANT`, or a
     hand-chosen constraint name (e.g. `fk_meetings_org`). If your change
     needs any of these, add the `op.execute(...)` calls yourself; see the
     baseline revisions (`d982478fc6e3`, `eec9dde1cfbb`, `87320bb9dc8d`) for
     concrete examples.
   - **Destructive or locking changes against real data** — adding
     `NOT NULL` to a populated column, a new unique index where duplicates
     may already exist, or any change that takes a long lock on a large
     table (`organizations` has 3000+ rows) will pass `alembic-check` (which
     only tests against an empty database) and still fail or lock in
     production. Prefer an expand/contract approach (add nullable → backfill
     → tighten in a later migration) for anything in this category.
4. Commit the model change and the migration file together, and open a PR.

### What happens automatically after that

- Any PR touching `server/**` runs `ci.yml`'s `alembic-check` job — applies
  every migration to a fresh throwaway Postgres and runs `alembic check` to
  catch drift between the models and the migrations, before merge. This
  proves the chain works **from empty** — it does not prove a migration is
  safe against an environment's real, populated data (see the destructive-
  change bullet above).
- Merging to `dev`/`prod` runs `_deploy.yml`'s "Run pending database
  migrations" step, which applies `alembic upgrade head` for real against that
  environment's actual RDS instance — via SSM against the toolkit EC2 instance,
  since RDS is `publicly_accessible = false` and GitHub Actions has no direct
  network path to it. This runs *before* the toolkit app itself is rolled to
  the new image, so a failed migration blocks the deploy rather than leaving
  new app code running against a schema it doesn't have yet.

### Onboarding an environment that predates Alembic

`dev` and `prod` both had their tables created by the (now-deleted) flat SQL
files before this Alembic chain existed — `alembic upgrade head` cannot run
against either of them from scratch, because the first real migration
(`87320bb9dc8d`, unguarded `op.create_table(...)`) would try to recreate
tables that already exist and fail with `DuplicateTable`. Both needed (or, for
`prod`, will need) a one-time `alembic stamp 87320bb9dc8d` run directly
against that environment before the normal CD pipeline can apply anything —
this tells Alembic "table creation already happened" without executing it,
so the grants revision and the two orphaned-column-drop revisions after it
still run for real. This is a one-time bootstrapping step per environment,
not something to repeat for ordinary schema changes.

## First-time or changed-schema setup

```powershell
uv run alembic -c .\alembic.ini upgrade head
```

Not required for every routine data sync -- only when the schema itself
changed.

## Running the sync

Always dry-run first. The dry run prints, per entity, how many records were
fetched, how many were excluded as `is_test`, and how many are still unstamped:

```text
organizations    fetched=3225 test_excluded=1 unstamped=3224
```

**Read those numbers before adding `-Apply`.** `sync-source-to-prod.ps1`
reconciles — `organizations` and `person` are soft-deleted via `removed_at`,
but `deals`, `buyer_roles` and `seller_roles` are **hard deletes with no
`removed_at` column**, so a record wrongly flagged `is_test` loses its row and
its `raw_attio` permanently. Recovery is an RDS point-in-time restore. A
greater-than-10% exclusion rate aborts the run rather than purging.

```powershell
./prod/sync-all-to-prod.ps1            # dry run
./prod/sync-all-to-prod.ps1 -Apply
./prod/validate-postgres.ps1
```

Once every existing SOURCE record has been stamped `is_test = false`, add
`-StrictIsTest` to make a nonzero `unstamped` count a failure — that turns a
write path which forgot to stamp into a loud error instead of a silent leak.

The sync is idempotent: existing rows update and missing rows insert without
creating duplicate identities. PostgreSQL-owned intelligence fields are not
replaced by Attio projections. Before commit the script verifies exact row
counts; any SQL, relationship, or count failure rolls back the transaction.

### Identity

```text
PostgreSQL attio_id = SOURCE Attio record ID
```

The legacy native-object ids remain available in `legacy_attio_id` and
`raw_attio`; they do not replace the key.

## Manager read-only access

Do not share the RDS master account. Create a dedicated read-only PostgreSQL
role with `CONNECT`, schema `USAGE`, and table `SELECT` only. The manager also
needs separately authorized AWS SSM access because RDS is private. Typical
DBeaver/pgAdmin settings after opening the tunnel are:

```text
Host: localhost
Port: 15432
Database: wusool_crm
SSL mode: require
Username: dedicated read-only role
```

Deliver the password through an approved password manager or Secrets Manager,
never Git, chat, screenshots, or email.
