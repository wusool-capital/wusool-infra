# Prod Postgres sync

Unlike [`../dev`](../dev), prod is **not** wired
to DEV Attio at all. It syncs directly from SOURCE Attio's own custom
objects (`organizations`, `person`, `deal`, `note`, and the `buyer_role`/
`seller_role` lists on them — built by
`workflows/crm-sync/scripts/source-attio/`), one hop shorter than the DEV
path (`SOURCE native -> SOURCE custom -> DEV custom -> Postgres`).

That one-hop difference means prod Postgres's `attio_id` is the SOURCE
custom object's own record id, not DEV's. `users` is still populated,
though -- via `/workspace_members`, a core workspace endpoint (not a custom
object), so it works the same on SOURCE as anywhere else and resolves
`owner_attio_id` on organizations/person/deals.

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
  `../dev/rds-tunnel-runbook.md` -- same mechanism, pointed at
  `wusool-prod-postgres` / the prod n8n instance / `eu-central-1`).
- `DATABASE_URL` for prod's `wusool_crm` through the tunnel.
- `SOURCE_ATTIO_API_KEY`.

## Routine synchronization

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\sync-all-to-prod.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\sync-all-to-prod.ps1 -Apply

powershell -NoProfile -ExecutionPolicy Bypass -File .\validate-postgres.ps1
```

Never share the RDS master password, complete admin `DATABASE_URL`, AWS keys,
or Attio keys.
