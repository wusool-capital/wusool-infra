# Dev Postgres sync

Syncs DEV Attio (the workspace this app's Slack bot actually writes to) into
the dev `wusool_crm` Postgres database: `organizations`, `person`, `deals`,
`buyer_roles`/`seller_roles`, `notes`. Notes are the one exception -- they
come from SOURCE Attio's own `note` object directly (DEV has no notes object
yet), bridged onto DEV-Attio-keyed `organizations`/`person` rows.

## Command surface

Run in this order (each step depends on the ones before it):

| Script | Responsibility |
| --- | --- |
| `sync-postgres.ps1` | Organizations -> People -> Deals -> Buyer Roles -> Seller Roles from DEV Attio, dry-run or `-Apply`. |
| `sync-notes-from-source.ps1` | Notes, from SOURCE's `note` object -- run *after* the above (needs organizations/person to already exist to resolve against). |
| `backfill-activities.ps1` | One-off historical backfill of the `activities` table's boundary-interaction timestamps, reading SOURCE directly (DEV collapsed the needed history down to single latest-value fields). |
| `validate-postgres.ps1` | Independently compare DEV Attio counts and validate key relationships. Read-only. |

## Prerequisites

- Python with `psycopg[binary]`.
- Active AWS SSM port-forwarding tunnel to dev's private RDS (see
  `rds-tunnel-runbook.md`).
- `DATABASE_URL` for dev's `wusool_crm` through the tunnel.
- `DEV_ATTIO_API_KEY`; `SOURCE_ATTIO_API_KEY` additionally for
  `sync-notes-from-source.ps1`/`backfill-activities.ps1`.

## Routine synchronization

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\sync-postgres.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\sync-postgres.ps1 -Apply

powershell -NoProfile -ExecutionPolicy Bypass -File .\validate-postgres.ps1
```

Never share the RDS master password, complete admin `DATABASE_URL`, AWS keys,
or Attio keys.
