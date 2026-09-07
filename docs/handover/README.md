# Wusool Infrastructure — Handover

This document describes the **current delivered state** of `wusool-infra`.
For development history see [`CHANGELOG.md`](../../CHANGELOG.md).

## 1. Overview

`wusool-infra` holds the OpenTofu configuration and the application code for
Wusool Capital's AWS environment. It delivers:

- **AWS infrastructure** for `dev` and `prod`, deployed automatically from
  Git by GitHub Actions.
- **The Wusool Toolkit Slack bot** — five slash commands for buyer–seller
  matching and for editing buyer/seller profiles.
- **An Attio ↔ PostgreSQL data platform** — the business CRM (Attio) kept in
  sync with a structured database (`wusool_crm`) used for automation,
  enrichment, and the matching engine.
- **n8n** — the workflow-automation platform, one instance per environment.

Everything runs in a single AWS account (`030179310793`) in `eu-central-1`
(Frankfurt). Terraform state is stored separately in `me-central-1`.

## 2. Delivered components

| Component | Status | Notes |
| --- | --- | --- |
| Continuous deployment (OpenTofu, GitHub OIDC) | **Live**, dev + prod | Merge to `dev` / `prod` applies changed stacks and health-checks the apps. No static AWS keys. |
| n8n | **Live**, dev + prod | Pinned image digests, HTTPS via Caddy, SMTP email working (sandbox mode). |
| Wusool Toolkit Slack bot | **Live** on dev; prod instance provisioned | One process, five commands. Prod compute instance is on (`create_instance = true`). |
| PostgreSQL (`wusool_crm`) on RDS | **Live** (dev); **provisioned** (prod) | Prod seeded from a dev snapshot, credentials rotated. Not yet the system of record for n8n's own data. |
| Schema management (Alembic + SQLAlchemy) | **Live** | Migrations are the schema source of truth; applied in CD via SSM. Dev fully migrated; confirm prod reached head (see Outstanding). |
| Attio → PostgreSQL sync | **Live** | Nightly full resync + real-time webhook (`POST /webhooks/attio`), both verified end-to-end. |
| AI matching (AWS Bedrock) | **Live** | Claude Haiku 4.5 (extraction) + Claude Sonnet 4.6 (reasoning) + Qwen3-235B, all in `eu-central-1`. |
| Security & monitoring baseline | **Live** | SSM (no SSH), Secrets Manager, CloudWatch logs/alarms, SNS email alerts, multi-region CloudTrail, account-wide GuardDuty + Security Hub. |
| Scribe database access (meetings) | **Partial** | Dev complete; dev↔prod VPC peering live; the real prod login credential is still pending (see Outstanding). |

## 3. Environments and URLs

| Item | Dev | Prod |
| --- | --- | --- |
| n8n | `https://n8n-dev.wusoolcapital.com/` | `https://n8n.wusoolcapital.com/` |
| Toolkit bot Slack Request URL | `https://63-184-6-136.sslip.io/slack/events` | Provisioned — read the live host with `tofu output` in `infrastructure/terraform/stacks/toolkit` |
| VPC CIDR | `10.10.0.0/16` | `10.20.0.0/16` |
| Region | `eu-central-1` | `eu-central-1` |

- AWS account: `030179310793`
- Terraform state: S3 bucket `wusool-tfstate` in `me-central-1`, key
  `wusool/<env>/<stack>/terraform.tfstate`
- Repository: `github.com/wusool-capital/wusool-infra` (default branch `dev`,
  production branch `prod`)
- DNS is managed in **Cloudflare**; records point at each environment's EC2
  Elastic IP.

## 4. Third-party services

| Service | Used for | Ownership |
| --- | --- | --- |
| AWS | All compute, database, AI, secrets, monitoring | Wusool AWS account `030179310793` |
| Attio | Business CRM of record; matching source data | Wusool Capital workspace ("SOURCE") — one workspace serves both environments, split by the `is_test` checkbox |
| Slack | The toolkit bot's only interface | One Slack app, one bot token (see `docs/dev/SLACK_APP_SETUP.md`) |
| Cloudflare | DNS for `*.wusoolcapital.com` | Wusool |
| GitHub / GitHub Actions | Source control and CI/CD; OIDC into AWS | `wusool-capital` org |
| AWS SES | n8n password-reset / invite email | `eu-central-1`, sandbox mode |
| AWS Bedrock | LLM calls for `/find-match` | `eu-central-1` |
| Firecrawl | Optional web-lead fallback in matching | API key optional; feature disables cleanly without it |
| n8n (self-hosted) | Workflow automation | Runs on Wusool EC2; vendor app |

## 5. Deployment and ownership

- **Infrastructure as code:** OpenTofu (not HashiCorp Terraform), version
  pinned in `infrastructure/terraform/.opentofu-version`.
- **Deploy trigger:** push to `dev` or `prod`. GitHub Actions builds the bot
  image to ECR (by digest), applies the changed OpenTofu stacks in
  dependency order, runs `alembic upgrade head` against RDS via SSM, rolls
  the app, and polls its health endpoint. `tofu apply`'s exit code alone is
  never trusted.
- **No manual approval gate** exists before a `prod` apply — this is a
  deliberate, documented accepted risk.
- **Secrets** live only in AWS Secrets Manager (`/wusool/<env>/n8n`,
  `/wusool/<env>/toolkit`). They are never in Git or in `*.tfvars`.
- **Alert email:** `raoof@azmora.ai` (SNS topic per environment).
- **Code ownership:** see `.github/CODEOWNERS`.

### Administrative access

- Shell access to EC2 instances is via **AWS Systems Manager Session
  Manager** — there is no SSH by default (`ssh_cidr_blocks` is empty).
- The database is **not publicly reachable**; reach it from the toolkit EC2
  instance (that is how CD runs migrations) or via an SSM port-forward
  tunnel.

### Cutover runbook: one SOURCE Attio workspace

None of this is in git. **The order is load-bearing**, and two steps in
particular are: `tofu apply` must precede each environment's code deploy, and
dev's Attio key must not be swapped until dev is already running the new code.
There is one SOURCE key, shared by both deployments — `ATTIO_IS_TEST` is what
separates them, not a second credential.
The failure mode of getting each wrong is stated.

| # | Step | Why here and not later |
| --- | --- | --- |
| P0 | Merge, and confirm whoever runs the prod sync scripts has pulled. | Those scripts run by hand, so merging is not enough. If dev starts writing test records to SOURCE before the operator's checkout has the `is_test` filters, the next `sync-all-to-prod.ps1 -Apply` writes them into production. |
| P1 | `GET /v2/webhooks` on SOURCE; confirm exactly one exists, targeting prod. | `sync-all-within-source.ps1`'s `Get-DevWebhook` silently skips its pause/resume safety if it finds anything other than exactly one — including `stamp-is-test.ps1`, which reuses that block. |
| P2 | `tofu apply` `stacks/toolkit` with `envs/prod.tfvars`. Confirm `/wusool/prod/toolkit` holds the SOURCE key. | **Must precede P3.** `ATTIO_IS_TEST` defaults to `true`, so prod running the new code without this templated in would ignore every inbound webhook, refuse the nightly resync, and stamp `is_test = true` on real records. Safe against the currently-deployed image, which does not read the variable. |
| P3 | Deploy the server code to **prod**. | From here prod filters `is_test` out of its ingest, stamps `false` on its own writes, and the nightly resync refuses to run in test scope. This is what makes P6 safe. |
| P4 | `tofu apply` `stacks/toolkit` with `envs/dev.tfvars`. | Sets `ATTIO_IS_TEST=true` explicitly. The code defaults to `true` anyway, so this is belt-and-braces rather than load-bearing. |
| P5 | Deploy the server code to **dev**. | Dev now stamps `is_test = true`, ignores Attio webhooks, and refuses cross-scope edits — but is still pointed at the DEV workspace, so none of it touches SOURCE yet. |
| P6 | **Only now** update `/wusool/dev/toolkit`'s `env`: `ATTIO_API_KEY` → the SOURCE key (the same one prod uses), drop `ATTIO_DEAL_OBJECT_SLUG`. Record the previous values first. | **Must follow P5.** This is the first moment dev writes to SOURCE. Done any earlier, the old dev image writes records with *no* `is_test` value — which reads as production — and prod ingests them as real CRM data. That is the one silent, hard-to-undo failure in this whole change. Value updates have no recovery window; the 30-day window is for secret *deletion*. |
| P7 | Delete the DEV-workspace webhook. Announce the local `.env` change: `ATTIO_API_KEY` becomes the SOURCE key, and `ATTIO_DEAL_OBJECT_SLUG` / `ATTIO_NOTE_OBJECT_SLUG` are both deleted. Clear the persisted user-scoped `DEV_ATTIO_API_KEY`. | `.env.example` is updated in the repo but existing `.env` files are untracked. Leaving the two deleted vars in a local `.env` is harmless (`extra="ignore"`), so this is tidy-up rather than a hard break. A stale user-scoped `DEV_ATTIO_API_KEY` invites a muscle-memory run against a dead workspace. |
| P8 | Run `server/scripts/postgres-sync/truncate-dev.ps1` (dry run, then `-Apply`). | After P5/P6, so devs are not creating test data into a database that is about to be emptied. |
| P9 | Run `infrastructure/crm-sync/scripts/source-attio/stamp-is-test.ps1` (dry run, then `-Apply`). | Order-independent — nothing depends on it, since the REST API's `eq false` filter matches unset records. Do it at leisure; it unblocks the Attio UI filters and `-StrictIsTest`. |
| P10 | Retire the DEV Attio workspace. | Last, and irreversible. Only after dev has been observed writing to SOURCE for a full working day. |

Never register a second SOURCE webhook pointing at dev, and never remove
`ATTIO_WEBHOOK_SECRET` from `/wusool/dev/toolkit`: `ddl_commands`' settings
require it unconditionally, so removing it fails `Settings()` on the first
request for *every* command, not just the Attio-writing ones. The dev route
ignores deliveries regardless.

Note that `tofu apply` on `stacks/toolkit` **stops and starts** the toolkit
instance and re-runs the SSM bootstrap, which is why P2 and P4 are separated per
environment rather than done as one apply. The Elastic IP association
survives, so the Slack request URL is unaffected.

Expect the nightly resync's per-table count check to fire **once** on its
first run after P3, for any test rows a dev instance leaked into production
before this change. That is the check doing its job, not a regression.

## 6. Known limitations

**Slack bot**

- No per-user authorization — any workspace member can run any command.
- No `/remove-seller` / `/remove-buyer` (built once, deliberately reverted).
- Two `/add-*` submissions for the same organization at the same time can
  both succeed and create a duplicate — no cross-request lock.
- Single process only: the in-memory idempotency store does not support
  running more than one instance.

**Matching engine**

- Web fallback is limited to Google-Maps leads and is never persisted.
- No semantic / vector retrieval, document ingestion, seller-financial
  enrichment, PDF generation, or outreach — these are out of scope by
  design.

**Infrastructure**

- Prod RDS is provisioned but is **not yet the system of record** for n8n's
  own data plane.
- The registered **prod n8n SSM bootstrap document lags the Terraform
  template**; re-running it can revert live fixes (Caddyfile, task-runner
  config). See `infrastructure/n8n/docs/infrastructure-overview.md` §18.
- AWS SES is in **sandbox mode** — each recipient email must be individually
  verified before it can receive n8n email.
- **Claude Sonnet 5** is blocked at the AWS account level; the reasoning
  step uses Claude Sonnet 4.6.

**Documentation**

- `infrastructure/n8n/docs/infrastructure-overview.md` predates both repo
  restructures — its structure/path sections are stale (content about n8n
  behaviour is still accurate).

## 7. Outstanding items

| Area | Item |
| --- | --- |
| Schema | Confirm prod reached Alembic `head` with the orphaned `removed_at` / `bot_managed_*` columns dropped after the migration step ran for real. |
| CRM migration | Investor/lender scope; scorecards scope; final owner/advisor backfill (currently `tech@wusoolcapital.com` as an approved stopgap); re-run the PostgreSQL sync against SOURCE Attio's current state and complete the Attio ↔ Postgres reconciliation audit. |
| Scribe (prod) | Create the real `scribe_pub` LOGIN role with a generated password on prod and hand the DSN to scribe as `WUSOOL_DATABASE_URL_PROD`. Until then scribe cannot publish prod meetings. |
| n8n | Update the registered prod `wusool-prod-n8n-bootstrap` SSM document to match the current template so re-runs stop reverting live fixes. |
| `is_test` stamping | Every SOURCE record created before 2026-09-07 has `is_test` unset. Not a blocker — the API's `eq false` filter matches unset records and the sync skips only an explicit `true` — but the Attio **UI** filter chips do not, so a human filtering on "Is Test" sees nothing from either environment until the records are stamped. **`infrastructure/crm-sync/scripts/source-attio/stamp-is-test.ps1` is written and committed but has never been run** — hand it to the data team. Dry-run by default; `-Apply` needs `-Confirmation STAMP_IS_TEST_FALSE_IN_SOURCE`. It writes only `is_test`, pauses the prod webhook for the run, and is idempotent. Suggest a bounded first pass (`-Entities organizations -Limit 20 -Apply ...`) before the full run. Do **not** use `sync-all-within-source.ps1 -Apply` instead: it re-runs the whole migration, layers every mapped field back over each record, and refires the webhook thousands of times. Once every "to stamp" column reads 0, add `-StrictIsTest` to the routine prod sync. |
| Dev database | Truncate the dev database at cutover — **`server/scripts/postgres-sync/truncate-dev.ps1` is written and committed but has never been run.** Every `attio_id` in it is a **DEV-workspace** record id and the dev bot now talks to SOURCE, so those rows are broken pointers, not merely stale: an `/edit-*` against one fails its scope read in a way that looks like a bot bug. Decided: Scribe's dev meeting data goes too (`CASCADE` reaches `meetings`, and the script lists the full closure in its dry run). Its `-Confirmation` token is derived from the connected server's address rather than being a fixed string, because through the tunnel dev and prod are both `localhost:15432/wusool_crm` and dev still holds ~3,000 orgs at cutover. |
| Dev seeding | A fresh dev database is empty, so `/find-match` has nothing to match against until someone creates a pool of buyer roles with `/add-buyer` — and each of those also creates an `is_test` org in the shared SOURCE workspace. If that becomes too slow, the right shape is a bounded sample copied **prod PostgreSQL → dev PostgreSQL**, never a second Attio consumer. |
| Nightly resync | Now writes the production database unattended, and a failure is only visible in the Actions tab. It deserves an `if: failure()` notification, but no workflow in this repo has one yet, so the mechanism (SNS via `stacks/base`'s `alarm_topic_arn`, or a Slack webhook) still needs choosing. |
| Docs tooling | `server/scripts/docs/generate-client-schema-overview.ps1` cannot run: its `database/sql` input was deleted 2026-08-29. Its two Attio paths were repointed when `dev-attio` was deleted, but fixing the rest means rewriting it to read the SQLAlchemy models in `server/app/models/` instead of `CREATE TABLE` text. |
| Docs (stale paths) | Roughly 20 places still reference a `workflows/crm-sync/...` or `database/...` path from before the directory restructure — including copy-pasteable run commands in `source-attio/README.md` that would fail as written. Pre-existing and unrelated to the `is_test` work, so left alone; the alembic docstrings among them should stay as they are, since they record why each migration existed at the time it ran. |
| Docs | Refresh `infrastructure/n8n/docs/infrastructure-overview.md` (predates both restructures); clear the stale "no prod toolkit instance yet" comment in `infrastructure/terraform/envs/prod.tfvars`; commit the `ATTIO_POSTGRES_REALTIME_SYNC.md` write-up if still wanted. |

## 8. Support and where to look

| Need | Start here |
| --- | --- |
| How to use the bot | [`docs/user-guide/README.md`](../user-guide/README.md) |
| Architecture, deployment, config | [`docs/technical/README.md`](../technical/README.md) |
| Change history | [`CHANGELOG.md`](../../CHANGELOG.md) |
| Terraform stack layout | [`infrastructure/terraform/README.md`](../../infrastructure/terraform/README.md) |
| Schema reference | [`server/SCHEMA.md`](../../server/SCHEMA.md), [`infrastructure/crm-sync/docs/CLIENT_SCHEMA_OVERVIEW.md`](../../infrastructure/crm-sync/docs/CLIENT_SCHEMA_OVERVIEW.md) |
| Slack app configuration | [`docs/dev/SLACK_APP_SETUP.md`](../dev/SLACK_APP_SETUP.md) |
| Scribe infra contract | [`docs/dev/SCRIBE_INFRA_CONTRACT.md`](../dev/SCRIBE_INFRA_CONTRACT.md) |
| Contributing / PR workflow | [`CONTRIBUTING.md`](../../CONTRIBUTING.md) |

### Safety rules

- Never commit state files, plan files, credentials, private keys, or local
  `terraform.tfvars`.
- Treat Terraform as the source of truth; reconcile any emergency console
  change back into it immediately.
- A repository review proves declared configuration, not live AWS state.
