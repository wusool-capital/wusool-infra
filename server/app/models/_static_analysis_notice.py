"""Shared disclaimer for the 14 models added in the "missing tables" batch
(`ALEMBIC_MIGRATION_HANDOVER.md`'s own list: `users`, `investor_lender_roles`,
`activities`, `deal_stage_events`, `signals`, `buyer_intel`,
`seller_financials`, `mandate_targets`, `documents`, `vertical_kb`,
`graph_edges`, `attio_sync_state`, `attio_raw_events`, `scorecards`).

Every file in that batch opens with a short comment pointing back here — read
this once, not fourteen times.

STATIC-ANALYSIS DRAFT, NOT A VERIFIED BASELINE
------------------------------------------------
These columns were derived by reading every file under `(historical, removed) database/sql/`
**end to end, in order**: `001_extensions.sql`, `002_core_attio_mirror.sql`,
`003_crm_roles.sql`, `004_machine_layer.sql`, `005_meetings.sql`,
`006_match_results.sql`, `007_org_name_trgm_index.sql`. That is the complete
set that exists in this repo as of 2026-08-17.

`ALEMBIC_MIGRATION_HANDOVER.md` describes the set as running through
`008_bot_managed_columns.sql`, and this batch's own task brief was written
assuming that file exists. It does not, on `dev`, today. `git log --all`
shows it was added (`973fe2b`, `0744d602`, `3b13dc5`) and then explicitly
reverted in `a880060` ("Reverts the previous bot-owned schema addition
(008_bot_managed_columns.sql, removed_at/bot_managed_at/bot_managed_by,
/remove-seller//remove-buyer) — schema changes are the data engineer's call,
not this bot's") — a commit that landed *before* the handover doc itself
(`d7d7211`) was written. So the handover doc's own "008" reference was
already stale the moment it was committed. Nothing in this batch depends on
that file; `investor_lender_roles`/`activities`/`buyer_intel`/etc. are all
fully defined by `004_machine_layer.sql`. Flagging this discrepancy rather
than inventing a plausible-looking `008` file to match the brief.

Per the handover doc's own point 5 ("Reflect the live database for the 14
missing tables' real columns — never the `.sql` files"), these flat SQL files
are **not guaranteed to match the live database**: conditional,
idempotency-guarded `ALTER TABLE`/`DO $$` blocks (e.g. `004_machine_layer.sql`
lines ~137-146's pgvector-column guard, and its ~148-190 rename guard for
`deals.exclusivity_start_date`/`exclusivity_end_date`) can leave different
environments in different states depending on when and in what order they
were applied there.

These 14 models are a **draft starting point for Stage 4's live-DB
reflection step** — not a verified final baseline. Whoever runs Stage 4 must
diff every one of them against a real `sqlalchemy.inspect()` or `psql \\d`
reflection of the live dev database before trusting any of this for
`alembic stamp head`.
"""
