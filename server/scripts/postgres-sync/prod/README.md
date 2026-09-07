# Prod Postgres sync

Syncs SOURCE Attio's own custom objects (`organizations`, `person`, `deal`,
`note`, and the `buyer_role`/`seller_role` lists on them — built by
[`infrastructure/crm-sync/scripts/source-attio/`](../../../../infrastructure/crm-sync/scripts/source-attio))
into the production database. `attio_id` is the SOURCE custom object's own
record id.

The standard plural `deals`, `companies` and `people` objects still exist in
SOURCE but are legacy: where a V2 object exists it is canonical, and only the
V2 objects carry `is_test`. The one exception is `backfill-activities.ps1`,
which reads the native objects deliberately — boundary-interaction timestamps
survive nowhere else — and crosswalks them to V2 ids via `legacy_attio_id`.

`users` is populated via `/workspace_members`, a core workspace endpoint
rather than a custom object, and resolves `owner_attio_id` on
organizations/person/deals.

There is no dev counterpart: the dev database is a sandbox, not a mirror. See
[`../README.md`](../README.md).

## Command surface

Run in this order (each step depends on the ones before it):

| Script | Responsibility |
| --- | --- |
| `sync-all-to-prod.ps1` | Single entry point through notes -- wraps the next two scripts in order, fails fast. Prefer this over running them separately. |
| `sync-source-to-prod.ps1` | Users -> Organizations -> People -> Deals -> Buyer Roles -> Seller Roles, dry-run or `-Apply`. |
| `sync-notes-from-source.ps1` | Notes, from SOURCE's `note` object -- run *after* the above (needs organizations/person/buyer_roles/seller_roles to already exist to resolve against). |
| `sync-meetings-from-source.ps1` | One-time backfill of `meetings` from SOURCE's native Granola-classified Company/Person notes (summary + who logged it + a link to the full transcript -- SOURCE has no raw transcript, participant list, duration, or audio file, so those stay NULL). Run after organizations/person above. |
| `backfill-activities.ps1` | One-off historical backfill of the `activities` table's boundary-interaction timestamps (not part of routine sync). |
| `validate-postgres.ps1` | Independently compare SOURCE counts and validate key relationships. Read-only. |

## Prerequisites

- Python with `psycopg[binary]`.
- Active AWS SSM port-forwarding tunnel to prod's private RDS (see
  `../rds-tunnel-runbook.md` -- same mechanism, pointed at
  `wusool-prod-postgres` / the prod n8n instance / `eu-central-1`).
- `DATABASE_URL` for prod's `wusool_crm` through the tunnel.
- `SOURCE_ATTIO_API_KEY`.

## `is_test`: what these scripts fetch

One SOURCE workspace has served both environments since 2026-09-07. Every
fetch here drops records flagged `is_test`, so the production database only
ever holds the production half.

Only an **explicit** `true` is dropped. An unset checkbox reads as production,
which is the state of every record migrated before that date — requiring an
explicit `false` would make these scripts fetch almost nothing and then let
the reconciliation below delete the production database.

Each entity prints its own line in the dry run:

```text
organizations    fetched=3225 test_excluded=1 unstamped=3224
```

`test_excluded` is how many test records were held back; `unstamped` is how
many have no `is_test` value yet. Once the stamping run has been done and
`unstamped` reads 0 everywhere, add `-StrictIsTest` to `sync-source-to-prod.ps1`
so a nonzero `unstamped` becomes a failure — that turns a write path which
forgot to stamp into a loud error rather than a silent leak into production.

`sync-notes-from-source.ps1` filters too, but has **no reconciliation pass**:
a test note that leaked in before this change is never purged.

## Read the dry run before you `-Apply`

Not folklore — a required step. `sync-source-to-prod.ps1` reconciles, and the
three role/deal tables reconcile by **hard delete**:

| Table | Not-fetched rows are |
| --- | --- |
| `organizations`, `person` | soft-deleted (`removed_at = now()`), recoverable |
| `deals`, `buyer_roles`, `seller_roles` | **`DELETE`d — no `removed_at` column** |

So a record wrongly flagged `is_test` loses its row and its `raw_attio`
permanently, and recovery is an RDS point-in-time restore. A non-zero
`test_excluded` on `deals` is a signal to stop and look. As a backstop, an
exclusion rate above 10% aborts the run instead of purging — the same shape as
the existing "SOURCE returned zero organizations" guards.

## Routine synchronization

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\sync-all-to-prod.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\sync-all-to-prod.ps1 -Apply

powershell -NoProfile -ExecutionPolicy Bypass -File .\validate-postgres.ps1
```

Never share the RDS master password, complete admin `DATABASE_URL`, AWS keys,
or Attio keys.
