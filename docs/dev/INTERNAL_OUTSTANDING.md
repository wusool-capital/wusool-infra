# Internal-only outstanding items

> Split out of `docs/handover/README.md` §7 when the handover doc became a
> client-facing GitBook page ([`docs/handover/outstanding.md`](../handover/outstanding.md)).
> These items are internal housekeeping — not client-relevant delivery
> status — so they stay here instead.

| Area | Item |
| --- | --- |
| Dev database | Truncate the dev database at cutover — **`server/scripts/postgres-sync/truncate-dev.ps1` is written and committed but has never been run.** Every `attio_id` in it is a **DEV-workspace** record id and the dev bot now talks to SOURCE, so those rows are broken pointers, not merely stale: an `/edit-*` against one fails its scope read in a way that looks like a bot bug. Decided: Scribe's dev meeting data goes too (`CASCADE` reaches `meetings`, and the script lists the full closure in its dry run). Its `-Confirmation` token is derived from the connected server's address rather than being a fixed string, because through the tunnel dev and prod are both `localhost:15432/wusool_crm` and dev still holds ~3,000 orgs at cutover. See [`ATTIO_SOURCE_CUTOVER.md`](ATTIO_SOURCE_CUTOVER.md) step 4. |
| Dev seeding | A fresh dev database is empty, so `/find-match` has nothing to match against until someone creates a pool of buyer roles with `/add-buyer` — and each of those also creates an `is_test` org in the shared SOURCE workspace. If that becomes too slow, the right shape is a bounded sample copied **prod PostgreSQL → dev PostgreSQL**, never a second Attio consumer. |
| `is_test` stamping | Every SOURCE record created before 2026-09-07 has `is_test` unset. Not a blocker — the API's `eq false` filter matches unset records and the sync skips only an explicit `true` — but the Attio **UI** filter chips do not, so a human filtering on "Is Test" sees nothing from either environment until the records are stamped. `infrastructure/crm-sync/scripts/source-attio/stamp-is-test.ps1` is written and committed but has never been run — hand it to the data team. Dry-run by default; `-Apply` needs `-Confirmation STAMP_IS_TEST_FALSE_IN_SOURCE`. It writes only `is_test`, pauses the prod webhook for the run, and is idempotent. Suggest a bounded first pass (`-Entities organizations -Limit 20 -Apply ...`) before the full run. Do **not** use `sync-all-within-source.ps1 -Apply` instead: it re-runs the whole migration, layers every mapped field back over each record, and refires the webhook thousands of times. Once every "to stamp" column reads 0, add `-StrictIsTest` to the routine prod sync. |
| Docs tooling | `server/scripts/docs/generate-client-schema-overview.ps1` cannot run: its `database/sql` input was deleted 2026-08-29. Its two Attio paths were repointed when `dev-attio` was deleted, but fixing the rest means rewriting it to read the SQLAlchemy models in `server/app/models/` instead of `CREATE TABLE` text. |
| Docs (stale paths) | Roughly 20 places still reference a `workflows/crm-sync/...` or `database/...` path from before the directory restructure — including copy-pasteable run commands in `source-attio/README.md` that would fail as written. Pre-existing and unrelated to the `is_test` work, so left alone; the alembic docstrings among them should stay as they are, since they record why each migration existed at the time it ran. |
| Docs | Refresh `infrastructure/n8n/docs/infrastructure-overview.md` (predates both repo restructures); clear the stale "no prod toolkit instance yet" comment in `infrastructure/terraform/envs/prod.tfvars`; commit the `ATTIO_POSTGRES_REALTIME_SYNC.md` write-up if still wanted. |

## Dropped item: `scribe_pub` prod credential

The previous outstanding list included "create the real `scribe_pub` LOGIN
role on prod and hand the DSN to Scribe as `WUSOOL_DATABASE_URL_PROD`."
That's superseded: `server/app/modules/meetings/` now owns writes to
`meetings` directly (the desktop app pushes transcripts to the server, which
writes the database itself) — see `SCRIBE_INFRA_CONTRACT.md`'s 2026-09-05
note. `scribe_pub` and Scribe's old EC2/SQS infrastructure are unused for
this purpose; decommissioning them is a separate follow-up, not tracked here.
