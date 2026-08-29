# DEV Attio to PostgreSQL

This folder defines the `wusool_crm` PostgreSQL schema and the transactional
sync from canonical DEV Attio. Attio owns human-facing CRM state; PostgreSQL
stores a relational mirror plus automation, history, analytics, and AI data.

## Command surface

| Script | Responsibility |
| --- | --- |
| `setup-postgres.ps1` | Apply four idempotent SQL schema files and validate required tables/columns. Optional guarded reset. |
| `sync-postgres.ps1` | Read canonical DEV Attio, map values, and dry-run or transactionally upsert PostgreSQL rows. As of 2026-08-28, writes every `buyer_role`/`seller_role` list entry (not just the active one per org -- see the "Mirroring every Attio record" note below). |
| `sync-notes-from-source.ps1` | The one exception to "DEV Attio -> PostgreSQL": populates `notes` directly from **SOURCE** Attio's `note` custom object (`workflows/crm-sync/scripts/source-attio/backfill-notes.ps1`), since DEV has no notes object yet. Bridges SOURCE record ids to Postgres's existing DEV-keyed rows via `organizations.raw_attio`/`people.raw_attio`'s `legacy_attio_id`. |
| `validate-postgres.ps1` | Independently compare DEV/PostgreSQL counts and validate key relationships. Read-only. |

### Mirroring every Attio record (2026-08-28)

`buyer_roles`/`seller_roles` used to be one row per organization
(`UNIQUE(org_attio_id)`), with `sync-postgres.ps1` silently dropping every
DEV Attio list entry except the active one before writing, specifically to
keep that constraint satisfiable. Per explicit product decision, Postgres
should mirror every Attio record that exists, full stop -- `is_active`
(already a column on both tables) is how a caller distinguishes the current
entry from stale duplicates, not something the sync script pre-filters on.

The unique constraint moved to `legacy_entry_id` (one row per DEV entry
instead of per org) via Alembic migration `b8f4c1e93a56`; `org_attio_id` is
now a plain indexed FK, so an org can have more than one `buyer_roles`/
`seller_roles` row. `Organization.buyer_role`/`.seller_role` became the
plural `buyer_roles`/`seller_roles` relationships in
`wusool_db/models/organization.py` to match. **Any consumer that assumed a
single buyer/seller role per organization must now filter to
`is_active=True` explicitly** -- this includes
`workflows/wusool-toolkit/matching-engine` and `.../ddl-commands` (Slack
`/edit-buyer`/`/edit-seller` and related), which have not been updated as
part of this change and should be checked before relying on this behavior
there.

## Prerequisites

- Python with `psycopg[binary]`.
- Active AWS SSM port-forwarding tunnel to private RDS.
- `DATABASE_URL` for `wusool_crm` through `localhost:15432`.
- `DEV_ATTIO_API_KEY` for synchronization.

See `rds-tunnel-runbook.md` for tunnel and credential retrieval commands.
Never share the RDS master password, complete admin `DATABASE_URL`, AWS keys,
or Attio keys.

## SQL schema files

`setup-postgres.ps1` reads `sql/*.sql`, sorts them by filename, and executes:

| File | Purpose |
| --- | --- |
| `001_extensions.sql` | Enable `pgcrypto`, `pg_trgm` (fuzzy organization-name search), and pgvector when available. |
| `002_core_attio_mirror.sql` | Create Users, Organizations, People, Deals, and Mandates. Organizations includes `removed_at timestamptz` (nullable; NULL means active) — `sync-postgres.ps1 -Apply` sets it when an org drops out of the DEV Attio organizations query and clears it if the org reappears. **Mandates retired 2026-08-23** (see below) — table kept for its 2 historical rows, but this file is frozen (see "flat SQL files are frozen" below) so the merge went through Alembic (`9c4d71ea2b56`), not here. |
| `003_crm_roles.sql` | Create Buyer Role, Seller Role, and optional investor/lender roles. |
| `004_machine_layer.sql` | Create activities, stage history, intelligence, matching, documents, graph, scorecards, reconciliation columns, and indexes. |
| `005_meetings.sql` | Create the `meetings` table (scribe-published buyer/seller meeting summaries) and enable `fk_meetings_org`. Not part of the Attio mirror — scribe is the sole writer. |
| `006_match_results.sql` | Create the `match_results` table for the matching-engine backend's Phase 3 Slack workflow (run audit, shortlisted candidates, status, approvals). Additive only — no existing table is touched. See `DOCS/migration/PHASE3_MATCH_RESULTS_HANDOVER.md` for full rationale. |
| `007_org_name_trgm_index.sql` | GIN trigram index on `organizations.name`, backing fuzzy/typo-tolerant buyer-name search. Requires `pg_trgm` from `001_extensions.sql`. |

All files (001-007) use `CREATE ... IF NOT EXISTS` and controlled `ALTER`
statements, so normal setup does not recreate tables or delete data.
`005_meetings.sql`'s `CREATE TYPE` statements and its `fk_meetings_org`
constraint have no native `IF NOT EXISTS` form in PostgreSQL, so they're
guarded with `DO $$ ... END $$` blocks that check `pg_type`/`pg_constraint`
before creating.

## Schema changes now go through Alembic, not new numbered SQL files

As of Phase G of `docs/Final_restructure_plan.md`, this folder is also a
Python package (`wusool_db/`,
`pyproject.toml`) holding the SQLAlchemy model for every table above, plus an
Alembic migration chain (`alembic.ini`, `alembic/`) that is now the source of
truth for **future** schema changes:

| Path | What it is |
| --- | --- |
| `wusool_db/models/` | One SQLAlchemy model per table, all registered on the one shared `Base` in `wusool_db/base.py`. Both `matching-engine` and `ddl-commands` import models from here — this is the *only* place any table is defined in Python. |
| `alembic/env.py` | Reads `DATABASE_URL` from the environment (the same secret the toolkit app itself already reads — never a new credential), imports every model so `--autogenerate` can see the full schema. |
| `alembic/versions/` | The actual migration files. `d982478fc6e3` → `87320bb9dc8d` → `eec9dde1cfbb` recreate everything `001`-`007` below produce, as the current baseline. |

### To make a schema change

1. Edit the relevant model(s) in `wusool_db/models/`. This is the single
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

- Any PR touching `database/**` runs `ci.yml`'s `alembic-check` job — applies
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

### The flat SQL files below are frozen — historical record only

**Do not add new numbered files to `sql/` and do not edit the existing ones.**
They remain as the historical record of how the schema reached its current
state, and `sync-postgres.ps1`/`validate-postgres.ps1` (Attio data sync, a
separate concern from schema) are unaffected by any of this. Per the handover
doc, deleting them outright is an explicit, separate future decision, not
automatic — but every *new* schema change from now on goes through Alembic,
never a new `sql/00N_*.sql` file.

### Onboarding an environment that predates Alembic

`dev` and `prod` both had their tables created by the flat SQL files above
before this Alembic chain existed — `alembic upgrade head` cannot run
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
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\database\setup-postgres.ps1
```

The script verifies `current_database()` is exactly `wusool_crm`, runs the SQL
files, and validates required tables and columns. It is not required for every
routine data sync.

## DEV extraction dry-run

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\database\sync-postgres.ps1
```

This reads, paginates, and maps:

```text
/workspace_members
/objects/organizations/records/query
/objects/person/records/query
/objects/deals/records/query
/lists/buyer_role/entries/query
/lists/seller_role/entries/query
/lists/mandates/entries/query
```

Raw API records and mapped rows exist temporarily in RAM. No CSV or staging
database is used. The dry-run prints counts and exits before connecting to
PostgreSQL.

## Apply DEV to PostgreSQL

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\database\sync-postgres.ps1 `
  -Apply
```

Sync order preserves foreign keys:

```text
Users -> Organizations -> People -> Deals -> Mandates -> Buyer Roles -> Seller Roles
```

**2026-08-23 Mandate/Deal merge:** `deals` gained 12 columns merged in from
`mandates` (`deal_type`, `universe_constructed`/`_size`,
`shortlist_approved`/`_size`, `tier1_contacted`, `responses`,
`counterparty_interested`, `mandate_start_date`/`mandate_expiry_date`,
`retainer_amount`, `source_mandate_entry_id`) via Alembic migration
`9c4d71ea2b56`. `mandates` itself is untouched, kept only for its 2
historical rows — nothing writes new rows there going forward. Run `alembic
upgrade head` (see "Schema changes now go through Alembic" below) before the
next `sync-postgres.ps1 -Apply`, or the new columns won't exist yet to sync
into.

The script uses parameterized `INSERT ... ON CONFLICT ... DO UPDATE` queries.
Core tables conflict on DEV `attio_id`; role tables conflict on
`org_attio_id`. The complete original Attio payload is also preserved in each
row's `raw_attio` JSONB column.

PostgreSQL identity rule:

```text
PostgreSQL attio_id = DEV Attio record ID
```

SOURCE identity remains inside DEV `legacy_attio_id` and `raw_attio`; it does
not replace the DEV key in PostgreSQL.

Before commit, the script verifies exact row counts. Any SQL, relationship, or
count failure rolls back the transaction.

## Last successful counts

| Table | Rows |
| --- | ---: |
| users | 1 |
| organizations | 3,040 |
| people | 4,329 |
| deals | 48 |
| buyer_roles | 264 |
| seller_roles | 172 |
| mandates | 2 |

## Routine synchronization

After DEV Attio is canonical, routine execution normally requires only:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\database\sync-postgres.ps1

powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\database\sync-postgres.ps1 -Apply

powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\database\validate-postgres.ps1
```

The sync is idempotent: existing rows update and missing rows insert without
creating duplicate DEV identities. PostgreSQL-owned intelligence fields are
not replaced by Attio projections.

The final validation command reads both systems, compares Users,
Organizations, People, Deals, Buyer Roles, Seller Roles, and Mandates, checks
critical foreign-key relationships, and returns a failing exit code on any
mismatch. It never writes to Attio or PostgreSQL.

## Destructive reset—exception only

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\database\setup-postgres.ps1 `
  -Reset -ConfirmDatabase wusool_crm
```

This drops the entire `public` schema. Never use it for routine setup or sync.

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
