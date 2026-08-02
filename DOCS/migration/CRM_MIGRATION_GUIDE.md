# CRM Migration

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
| People | Person | `people` |
| Deals | Deals | `deals` |
| Buyer Brain | Buyer Role | `buyer_roles` |
| Valuation Tool Leads | Seller Role | `seller_roles` |
| Buy-side Mandates | Mandates | `mandates` |
| DEV members | Users | `users` |

Important rules:

- SOURCE Attio is never modified.
- Relationship Status is an optional single select normalized to Warm, Cold,
  or Closed.
- Deal `associated_company` maps to Seller; historical Buyer stays empty when
  SOURCE has no approved buyer reference.
- Deal readiness values are stored as Boolean/null.
- Exclusivity start and end dates remain separate.
- PostgreSQL relationships store Attio IDs; names are displayed using joins.
- Missing or ambiguous historical values remain null rather than being guessed.

The executable mapping is in `scripts/attio/config/`.

## Scripts

Attio:

| Script | Purpose |
| --- | --- |
| `ensure-schema.ps1` | Validate/create the approved DEV schema. |
| `sync-objects.ps1` | Sync Organizations, Persons, and Deals. |
| `sync-lists.ps1` | Sync Buyer Role, Seller Role, and Mandates. |
| `validate-attio.ps1` | Compare SOURCE and DEV counts. |

PostgreSQL:

| Script | Purpose |
| --- | --- |
| `setup-postgres.ps1` | Apply and validate the database schema. |
| `sync-postgres.ps1` | Preview or apply DEV-to-PostgreSQL upserts. |
| `validate-postgres.ps1` | Compare DEV/PostgreSQL counts and relationships. |

Full commands are documented in `scripts/attio/README.md` and
`scripts/db/README.md`.

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
