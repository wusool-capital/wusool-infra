# ddl-commands

`/edit-seller`, `/remove-seller`, `/edit-buyer`, `/remove-buyer` — editing
and soft-deleting buyer/seller profiles directly against `wusool_crm`.

**Not independently deployed.** This is one of two folders that make up a
single Slack bot — see `../README.md` for how this fits together with
`../matching-engine/` and how the bot actually runs (`../main.py`, one
process, one Slack app). This folder's own `ddl_commands/main.py` still
exists and works (its own test suite uses it), but it is not the deployed
entrypoint.

`/add-seller` is intentionally not implemented yet — it depends on an
unresolved decision about whether this bot may create new `organizations`
rows or must always attach to an org that already exists via Attio.

## Running this folder standalone (for isolated dev/testing only)

```bash
cd workflows/wusool-toolkit/ddl-commands
uv sync
cp .env.example .env  # then fill in real values
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

## Data model

Reads/writes `organizations`, `buyer_roles`, `seller_roles` in the same
`wusool_crm` database matching-engine uses — see `../../../database/README.md`
for the schema. This bot never creates tables or runs migrations; the
`removed_at`/`bot_managed_at`/`bot_managed_by` columns these commands depend
on come from `database/sql/008_bot_managed_columns.sql`, applied the same way
as every other migration in that folder. matching-engine's own
`SellerRole`/`BuyerRole` models also map these same 3 columns (added when
the two bots were merged into one process) so `/find-match` excludes
removed rows too — see `../matching-engine/README.md`.

**Soft delete, not hard delete**: `/remove-seller`/`/remove-buyer` set
`removed_at` rather than issuing a SQL `DELETE` — `match_results.buyer_role_id`/
`seller_role_id` are `ON DELETE CASCADE`, so a hard delete would silently wipe
approve/reject match history in matching-engine. Removed rows are excluded
from `/edit-*`'s and `/remove-*`'s default fuzzy search, but `/edit-seller`/
`/edit-buyer` can still find one (labeled `(removed)`) and restore it —
gated behind a required confirmation checkbox on the edit form, not a side
effect of a routine save.

**Sync-collision guard**: `buyer_roles`/`seller_roles` are normally fully
owned by `database/sync-postgres.ps1`'s periodic Attio upsert — every
business column on both tables gets overwritten on every sync run. Once this
bot writes a row (`bot_managed_at` set), that sync script skips overwriting
it on every future run (`ON CONFLICT ... WHERE bot_managed_at IS NULL`) and
posts a warning to `SYNC_ALERT_WEBHOOK_URL` if configured — this is
**permanent** for the life of that row, not a temporary lock. See
`../../../database/sync-postgres.ps1` for the full reasoning.

## Out of scope (for now)

- `/add-seller` — see above.
- Any authorization/allowlist restricting who can run these commands.
- A full audit history of every actor who's touched a row — `bot_managed_by`
  is last-writer-wins only.
- Horizontal scaling — the in-memory idempotency store is single-process
  only, same limitation matching-engine already has.
