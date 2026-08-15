# ddl-commands

Slack bot for editing/removing buyer and seller profiles directly against
`wusool_crm` — `/edit-seller`, `/remove-seller`, `/edit-buyer`,
`/remove-buyer`. Python FastAPI + Slack Bolt, its own Postgres access, its
own Slack app (separate `SLACK_BOT_TOKEN`/`SLACK_SIGNING_SECRET` from
`../matching-engine`, which owns `/find-match` and is unaffected by this bot).

`/add-seller` is intentionally not implemented yet — it depends on an
unresolved decision about whether this bot may create new `organizations`
rows or must always attach to an org that already exists via Attio.

## Setup

```bash
cd workflows/wusool-toolkit/ddl-commands
uv sync
cp .env.example .env  # then fill in real values
```

## Running

```bash
uv run uvicorn app.main:app --reload
```

- `GET /health` — liveness, no database dependency.
- `GET /readiness` (alias `GET /ready`) — confirms database connectivity.
- `POST /slack/events` — the Slack callback endpoint (slash commands,
  interactive actions, view submissions). Signature-verified by Bolt.

### Configuring the Slack app

1. Create a **separate** Slack app at api.slack.com/apps — do not reuse
   matching-engine's app/token.
2. **Slash Commands** → create `/edit-seller`, `/remove-seller`,
   `/edit-buyer`, `/remove-buyer`, request URL `https://<your-host>/slack/events`.
3. **Interactivity & Shortcuts** → enable, same request URL.
4. **OAuth & Permissions** → bot token scopes: `commands`, `chat:write`.
   Install to the workspace; copy the bot token into `SLACK_BOT_TOKEN`.
5. **Basic Information** → copy the Signing Secret into `SLACK_SIGNING_SECRET`.

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
as every other migration in that folder.

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
`../../../database/sync-postgres.ps1` and `plan.md` for the full reasoning.

## Out of scope (for now)

- `/add-seller` — see above.
- Any authorization/allowlist restricting who can run these commands.
- A full audit history of every actor who's touched a row — `bot_managed_by`
  is last-writer-wins only.
- Horizontal scaling — the in-memory idempotency store is single-process
  only, same limitation matching-engine already has.
