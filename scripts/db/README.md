# DEV Attio to PostgreSQL

This folder defines the `wusool_crm` PostgreSQL schema and the transactional
sync from canonical DEV Attio. Attio owns human-facing CRM state; PostgreSQL
stores a relational mirror plus automation, history, analytics, and AI data.

## Command surface

| Script | Responsibility |
| --- | --- |
| `setup-postgres.ps1` | Apply four idempotent SQL schema files and validate required tables/columns. Optional guarded reset. |
| `sync-postgres.ps1` | Read canonical DEV Attio, map values, and dry-run or transactionally upsert PostgreSQL rows. |
| `validate-postgres.ps1` | Independently compare DEV/PostgreSQL counts and validate key relationships. Read-only. |

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
| `001_extensions.sql` | Enable `pgcrypto` and pgvector when available. |
| `002_core_attio_mirror.sql` | Create Users, Organizations, People, Deals, and Mandates. |
| `003_crm_roles.sql` | Create Buyer Role, Seller Role, and optional investor/lender roles. |
| `004_machine_layer.sql` | Create activities, stage history, intelligence, matching, documents, graph, scorecards, reconciliation columns, and indexes. |
| `005_meetings.sql` | Create the `meetings` table (scribe-published buyer/seller meeting summaries) and enable `fk_meetings_org`. Not part of the Attio mirror — scribe is the sole writer. |
| `006_match_results.sql` | Create the `match_results` table for the matching-engine backend's Phase 3 Slack workflow (run audit, shortlisted candidates, status, approvals). Additive only — no existing table is touched. Not yet applied against `wusool_crm`; see `DOCS/migration/PHASE3_MATCH_RESULTS_HANDOVER.md` for full rationale. |

Files 001-004 (and 006) use `CREATE ... IF NOT EXISTS` and controlled `ALTER`
statements, so normal setup does not recreate tables or delete data.
**`005_meetings.sql` does not follow this convention** — its `CREATE TYPE`/
`CREATE TABLE` statements have no `IF NOT EXISTS` guard, so re-running
`setup-postgres.ps1` after it has been applied once will fail trying to
recreate the existing types/table. Fine for the one-time apply already done
against `wusool_crm`, but worth guarding before any future full re-run.

## First-time or changed-schema setup

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\db\setup-postgres.ps1
```

The script verifies `current_database()` is exactly `wusool_crm`, runs the SQL
files, and validates required tables and columns. It is not required for every
routine data sync.

## DEV extraction dry-run

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\db\sync-postgres.ps1
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
  -File .\scripts\db\sync-postgres.ps1 `
  -Apply
```

Sync order preserves foreign keys:

```text
Users -> Organizations -> People -> Deals -> Mandates -> Buyer Roles -> Seller Roles
```

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
  -File .\scripts\db\sync-postgres.ps1

powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\db\sync-postgres.ps1 -Apply

powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\db\validate-postgres.ps1
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
  -File .\scripts\db\setup-postgres.ps1 `
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
