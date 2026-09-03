u# CRM Migration

See also:

- [Client schema overview](CLIENT_SCHEMA_OVERVIEW.md) — Attio and PostgreSQL
  schema reference for the migration target model

## Overview

```text
Legacy SOURCE Attio (read-only)
        -> DEV Attio
        -> PostgreSQL (wusool_crm)
```

DEV Attio is the human-facing CRM. PostgreSQL is the reporting, automation,
history, and intelligence layer. DEV stores each SOURCE record ID in
`legacy_attio_id`; PostgreSQL stores DEV record IDs in `attio_id`. These stable
IDs make reruns update existing records instead of creating duplicates.

## Data mapping

| SOURCE | DEV Attio | PostgreSQL |
| --- | --- | --- |
| Companies | Organizations | `organizations` |
| People | Person | `person` |
| Deals | Deals | `deals` |
| Buyer Brain | Buyer Role | `buyer_roles` |
| Valuation Tool Leads | Seller Role | `seller_roles` |
| Buy-side Mandates | Mandates *(retired 2026-08-23, see below)* | `mandates` |
| DEV members | Users | `users` |

**2026-08-23 Mandate/Deal merge:** the DEV Mandates list is retired — every
Mandate entry becomes its own Deal record instead (`stage` = `Mandate
Active`, a signed mandate still sourcing candidates with no specific
counterparty yet). One-time, idempotent migration via `sync-all.ps1
-Entities deals -MigrateMandates`. Details and full field mapping in
[Client schema overview](CLIENT_SCHEMA_OVERVIEW.md#mandate--retired-2026-08-23-merged-into-deal).
The PostgreSQL `mandates` table has not been updated to match — follow-up work.

**Deal owner for automation-created inbound leads:** ValuationTool and n8n
Integration (the SOURCE identities that create inbound leads) resolve via
`workspace_member_crosswalk` in `scripts/config/migration-decisions.json` to
Ramzy's DEV stand-in, not the generic tech@ account — see the crosswalk
entries' `note` fields for why. `assigned_advisor` on Deal is unrelated: it's
a separate multiselect `Hugo`/`Jules`/`Ramzy` field, not derived from `owner`.

Important rules:

- SOURCE Attio is never modified.
- Relationship Status is an optional single select normalized to Warm, Cold,
  or Closed.
- Deal `associated_company` maps to Seller; historical Buyer stays empty when
  SOURCE has no approved buyer reference.
- Deal readiness values are stored as Boolean/null.
- Exclusivity dates remain two separate columns: `contract_signed_date`
  (formerly the exclusivity start date) and `exclusivity_date` (formerly the
  exclusivity end date).
- PostgreSQL relationships store Attio IDs; names are displayed using joins.
- Missing or ambiguous historical values remain null rather than being guessed.

The executable mapping is in `workflows/crm-sync/scripts/dev-attio/config/`.

## Scripts

Attio:

| Script | Purpose |
| --- | --- |
| `sync-all.ps1` | Single entry point for a full migration run: wraps `sync-objects.ps1`/`sync-lists.ps1` in the required order (`organizations -> person -> buyer_role -> seller_role -> deals -> mandates`), fails fast on the first error, supports running a subset via `-Entities`. Prefer this over the two scripts below unless you need one in isolation. `-Entities deals -DeleteOrphaned` deletes DEV Deals whose `legacy_attio_id` no longer exists in SOURCE (a SOURCE Deal deleted after migration). `-Entities deals -MigrateMandates` runs the one-time Mandate-to-Deal migration (see above) after the normal deals sync completes, in the same run. Both are idempotent and safe to re-run. |
| `ensure-schema.ps1` | Validate/create the approved DEV schema. |
| `sync-objects.ps1` | Sync Organizations, Persons, and Deals. |
| `sync-lists.ps1` | Sync Buyer Role, Seller Role, and Mandates. |
| `backfill-seller-intake-source.ps1` | One-off backfill for Seller Role `intake_source` (not part of the recurring sync — see `FIELD_DECISIONS.md`). |
| `validate-attio.ps1` | Compare SOURCE and DEV counts. |

PostgreSQL:

| Script | Purpose |
| --- | --- |
| `setup-postgres.ps1` | Apply and validate the database schema. |
| `sync-postgres.ps1` | Preview or apply DEV-to-PostgreSQL upserts. |
| `validate-postgres.ps1` | Compare DEV/PostgreSQL counts and relationships. |

Full commands are documented in `workflows/crm-sync/scripts/dev-attio/README.md` and
`database/README.md`.

## Execution order

1. Run Attio schema and sync dry-runs.
2. Apply objects, then lists.
3. Run `validate-attio.ps1`.
4. Open the private PostgreSQL SSM tunnel.
5. Run `setup-postgres.ps1`.
6. Run `sync-postgres.ps1`, then `sync-postgres.ps1 -Apply`.
7. Run `validate-postgres.ps1`.

Last successful baseline: 1 user, 3,040 organizations, 4,329 people, 48 deals,
264 buyer roles, 172 seller roles, and 2 mandates. New user data can increase
these counts.

## Safety

- All syncs default to dry-run and all applies are idempotent.
- Never commit API keys, AWS credentials, database passwords, `.env` files, or
  runtime output.
- PostgreSQL is private and accessed through SSM on local port `15432`.
- Managers use individual AWS identities and dedicated read-only database users.
