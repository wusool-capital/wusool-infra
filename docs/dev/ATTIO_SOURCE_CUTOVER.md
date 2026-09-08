# Cutover runbook: one SOURCE Attio workspace

> Moved from `docs/handover/README.md` §5 when the handover doc was split
> into a client-facing GitBook (dev/prod internals don't belong there). This
> content is unchanged from the original.

`_deploy.yml` already applies the `toolkit` stack (it triggers on
`infrastructure/terraform/modules/toolkit-ec2/**` and `server/**`, both of
which this change touches), runs `alembic upgrade head`, regenerates
`/opt/toolkit/toolkit/.env.production` from Secrets Manager, and rolls the
container. So a merge does the terraform apply and the code deploy together —
there is no manual `tofu apply` in this sequence.

**The one thing that must not be reordered: prod is deployed before dev's
Attio key is swapped.** Everything else is tidy-up.

| # | Step | Why here |
| --- | --- | --- |
| 1 | Merge to `dev`. | Sets `ATTIO_IS_TEST=true`, deploys the new code. Dev's secret still holds the **DEV** key, so dev is still writing to the old workspace and nothing touches SOURCE yet. Safe to sit here indefinitely. |
| 2 | Merge to `prod`. | Sets `ATTIO_IS_TEST=false` and puts the ingest filter live, so prod now drops `is_test = true` records and the nightly resync is allowed to run. **This is what makes step 3 safe.** |
| 3 | Swap `/wusool/dev/toolkit`'s `env.ATTIO_API_KEY` to the SOURCE key, then **re-invoke the bootstrap SSM document directly**: `aws ssm send-command --instance-ids <dev toolkit> --document-name wusool-dev-toolkit-bootstrap`. | **Must follow step 2.** This is the first moment dev writes to SOURCE. Do it before prod is deployed and the old prod image — which has no filter — ingests dev's test records as real CRM data. Silent, and exactly what this change exists to prevent. **Do not use a `workflow_dispatch` re-run of Deploy dev for this** — verified 2026-09-07: with no path changes since the last deploy, `_deploy.yml`'s change detection sets every stack to `false` and skips the toolkit roll, so the run reports success while `.env.production` is never regenerated and the container keeps the old key. Invoking the bootstrap document is what actually rewrites the file and restarts the container. Rollback is `update-secret-version-stage` to move `AWSCURRENT` back to the `AWSPREVIOUS` version: Secrets Manager retains the prior value automatically, so a value update is reversible (the 30-day recovery window is for secret *deletion*, which is a different thing). |
| 4 | `server/scripts/postgres-sync/truncate-dev.ps1` — dry run, then `-Apply -Confirmation <token the dry run prints>`. | Every `attio_id` in the dev database is a DEV-workspace id, so after step 3 they are broken pointers: an `/edit-*` against one fails its scope read in a way that looks like a bot bug. Takes `meetings` with it (Scribe's dev data) — by decision. |
| 5 | `infrastructure/crm-sync/scripts/source-attio/stamp-is-test.ps1` — dry run, then `-Apply -Confirmation STAMP_IS_TEST_FALSE_IN_SOURCE`. | Order-independent; nothing depends on it. Hand to the data team. Unblocks the Attio UI's "Is Test" filter and `-StrictIsTest` on the prod sync. |
| 6 | Delete the DEV-workspace webhook. Tell developers to point their local `.env`'s `ATTIO_API_KEY` at the SOURCE key. Clear the persisted user-scoped `DEV_ATTIO_API_KEY`. | Left alone, the DEV webhook keeps retrying against the dev toolkit. `ATTIO_DEAL_OBJECT_SLUG` and `ATTIO_NOTE_OBJECT_SLUG` are both deleted settings now — leaving them in a local `.env` is inert under `extra="ignore"`, so that part is tidy-up. |
| 7 | Retire the DEV Attio workspace. | Last, and irreversible. Only after a full working day of dev writing to SOURCE. |

Before step 1, confirm whoever runs the prod sync scripts by hand has pulled:
those are not deployed, so an operator on a stale checkout would run a
`sync-all-to-prod.ps1 -Apply` with no `is_test` filter.

Never register a second SOURCE webhook pointing at dev, and never remove
`ATTIO_WEBHOOK_SECRET` from `/wusool/dev/toolkit`: `ddl_commands`' settings
require it unconditionally, so removing it fails `Settings()` on the first
request for *every* command, not just the Attio-writing ones. The dev route
ignores deliveries regardless.

There is one SOURCE key, shared by both deployments. `ATTIO_IS_TEST` is what
separates them, not a second credential.

Expect the nightly resync's per-table count check to fire **once** on its
first run after step 2, for any test rows a dev instance leaked into
production before this change. That is the check doing its job.
