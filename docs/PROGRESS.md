# Project Progress

Single entry point for "what has been done so far" across every workstream in
this repository. Read this file first in a new session before digging through
git history or chat logs. Detailed, granular status for each workstream lives
in its own document (linked below) — this file stays a short, high-level
index and is kept current by the `sync-project-docs` skill (or manually,
see [Keeping this file current](#keeping-this-file-current)).

Last updated: 2026-08-18

## Workstreams

### 1. Infrastructure (OpenTofu / n8n / toolkit) — full CD restructure landed; both dev and prod deployed and OIDC-driven

Superseded by the 2026-08-16 CD restructure (PR #26, `plan-cd-restructure` →
`dev`) — the prod-orphaned/dual-domain/SMTP narrative below predates it and
no longer reflects live state. Everything that used to be described inline
here now lives in three purpose-built docs, so it isn't duplicated a fourth
time in this index:

- [`CD_RESTRUCTURE_RESULT.md`](CD_RESTRUCTURE_RESULT.md) — **start here.**
  Concise before/after of what changed and what's now enforced (stacks
  layout, OIDC auth, ECR digest deploys, AMI pinning, what's explicitly
  deferred).
- [`RESTRUCTURE_PROGRESS.md`](RESTRUCTURE_PROGRESS.md) — the detailed,
  phase-by-phase execution log with verification evidence for every step.
- [`Final_restructure_plan.md`](Final_restructure_plan.md) — the original
  design document (historical; read the two docs above for what actually
  shipped, which differs from this in places).

In short: both dev and prod are real, deployed environments in one account,
applied via GitHub Actions on merge to `dev`/`prod`, authenticated by OIDC
(no static AWS keys). n8n is pinned to `n8n.wusoolcapital.com` in both
Terraform and DNS (the dual-domain/Terraform-orphaned prod gap this section
used to describe is resolved). See
[workflows/n8n/docs/infrastructure-overview.md](../workflows/n8n/docs/infrastructure-overview.md)
for n8n-specific operational detail (SMTP, the stdlib task-runner config fix,
etc.) — that document was not part of the restructure and remains current.

**Since the restructure landed, toolkit-specific hardening merged on top of
it (PRs #29, #31–#33, #37–#39):** the prod `wusool-toolkit` EC2 instance was
switched on for real (`create_instance = true`), the SSM
bootstrap/docker-compose-recreate cycle gained retries for a couple of
transient races, the `gha_apply` role picked up a missing
`iam:TagInstanceProfile` permission it needed, app logs now ship to
CloudWatch tagged by module, and the shared Docker build picked up a fix for
copying the `shared/` workspace member correctly. All routine, all merged
through `dev` → `prod` the normal way — no open follow-up from any of these.

### 6. Database schema management (SQLAlchemy + Alembic) — Phase G landed; dev fully migrated, prod bootstrapping in progress

- **Done (2026-08-18, PR #45):** every table's SQLAlchemy model relocated
  into `database/wusool_db/models/` as the single source of truth —
  `matching-engine` and `ddl-commands` no longer define any model of their
  own, both just import from here. An Alembic migration chain
  (`database/alembic/`) now owns schema changes going forward; `ci.yml`'s
  `alembic-check` job validates every PR's migrations against a fresh
  throwaway Postgres, and `_deploy.yml` applies `alembic upgrade head` for
  real via SSM against each environment's RDS before the app rolls to new
  code. See `database/README.md` for the full day-to-day workflow.
- **Dev verified live (2026-08-18):** `alembic_version` = `6b0642671e13`
  (head), all 23 tables present and matching the models exactly, the two
  orphaned `removed_at`/`bot_managed_at`/`bot_managed_by` columns (dead
  leftovers from reverted PR #23) confirmed dropped from both
  `buyer_roles`/`seller_roles`, row counts unchanged (279/210/3137)
  confirming zero data loss.
- **Prod (2026-08-18):** `stacks/postgres` for prod predates Alembic — its
  23 tables were already there from the old flat-SQL setup, with no
  `alembic_version` bookkeeping and the same orphaned columns still present.
  Stamped `alembic_version` at `87320bb9dc8d` directly (bookkeeping only, no
  schema change) so the pending grants + orphan-column-drop migrations can
  still apply for real on the next deploy instead of the chain failing
  outright on `DuplicateTable`. PR #46 ("Dev -> prod promotion") is open to
  actually ship this to prod — not yet merged as of this update.
- **Not yet done:** confirm prod ends at head with the orphan columns
  dropped after PR #46 merges and the CD migration step runs for real (see
  `database/README.md`'s "Onboarding an environment that predates Alembic").

### 2. CRM / data-platform migration (Attio + PostgreSQL) — core objects migrated and re-synced, tail work remains

High-level summary only — the authoritative, field-by-field decision log is
maintained separately as local assistant working memory (not part of this
repo) per `AGENTS.md`; consult that when doing further Attio/Postgres work.

**Done:**
- Organization, Person, Buyer Role, Seller Role, Mandates, and Deal objects
  migrated SOURCE Attio → DEV Attio, idempotent by `legacy_attio_id`.
- Added `workflows/crm-sync/scripts/sync-all.ps1` (2026-08-08/09): single entry point for
  a full migration run, wrapping the existing `sync-objects.ps1`/
  `sync-lists.ps1` in the required dependency order (`organizations ->
  person -> buyer_role -> seller_role -> deals -> mandates`), fails fast on
  the first error, supports running a subset by name, and parallel workers
  where the underlying scripts support it. See
  [workflows/crm-sync/scripts/README.md](../workflows/crm-sync/scripts/README.md).
- Ran a full re-sync via `sync-all.ps1` (2026-08-09) after several Attio
  decisions/fixes landed the same day: the `exclusivity_date` split-field
  rename, Buyer Role `deal_structure_tolerance` converted to a single-select
  (Majority/Minority/Flexible/Acquisition Financing), and Seller Role
  `sell_timeline`/`intake_source` option sets corrected and backfilled — see
  the migration context `FIELD_DECISIONS.md`/`DAILY_LOG.md` for the full
  rationale on each. The 4 new SOURCE Deals since the original migration
  were created using the existing approved temporary owner
  (`tech@wusoolcapital.com`) — this is a stopgap, not the final owner/advisor
  mapping (see below).
- Also fixed a real Deal-sync gap during this work: it previously assumed no
  DEV Organization for a Deal's seller could be missing; now self-heals by
  creating a minimal Seller Role entry when a resolved seller Organization
  doesn't have one yet, instead of leaving `seller_id` and Seller Role
  silently out of sync.
- PostgreSQL schema (migrations 001–004, consolidated) previously applied
  with a full DEV extraction mirrored in; record counts there predate this
  latest Attio re-sync and need refreshing (see "Not started" below).
- Attio/PostgreSQL and CRM migration scripts consolidated (see
  [CRM_MIGRATION_GUIDE.md](../workflows/crm-sync/docs/CRM_MIGRATION_GUIDE.md) and
  [CLIENT_SCHEMA_OVERVIEW.md](../workflows/crm-sync/docs/CLIENT_SCHEMA_OVERVIEW.md)).

**Not started:**
- Investor/lender scope
- Scorecards scope
- Final owner/advisor backfill — `tech@wusoolcapital.com` is an approved
  stopgap for creating new Deals, not a resolution of the underlying DEV
  workspace member mapping (still blocked as of the last check: 4 SOURCE
  members, 1 DEV member, 1 exact match, 3 unmatched).
- Re-run the PostgreSQL sync against DEV Attio's current state (record
  counts there are stale relative to today's Attio re-sync) and the full DEV
  Attio ↔ PostgreSQL reconciliation audit.

### 3. AI / AWS Bedrock — done: all 3 models confirmed working via Terraform

- Scoped 2026-08-07, built and applied 2026-08-08: new
  `terraform/modules/bedrock-access` Terraform module grants the existing n8n EC2
  instance role (`wusool-dev-n8n-ec2`) `bedrock:InvokeModel`/
  `InvokeModelWithResponseStream` on specific foundation models, wired into
  `terraform/environments/dev`. See `terraform/modules/bedrock-access/` and
  `terraform/environments/dev/variables.tf` (`bedrock_models`).
- **2026-08-09: swapped `anthropic.claude-sonnet-5` → `anthropic.claude-sonnet-4-6`.**
  Sonnet 5 stayed blocked by an Anthropic account-level access review
  (`AccessDeniedException`, "not available for this account ... contact AWS
  Sales") with no fixed timeline — confirmed via CLI, inference profile, and
  the console Playground, not a config/credentials issue. Sonnet 4.6 has no
  such restriction and is fully working. Like Haiku, it requires a
  cross-region inference profile (`eu.anthropic.claude-sonnet-4-6` — bare
  on-demand ID returns a `ValidationException`); confirmed via
  `aws bedrock list-inference-profiles --region eu-central-1`.
- **Final model set, all in `eu-central-1` (Frankfurt) — all 3 confirmed
  PASS via `workflows/bedrock-ai/scripts/test-bedrock-models.ps1`:**
  - `anthropic.claude-sonnet-4-6` via inference profile `eu.anthropic.claude-sonnet-4-6`
  - `anthropic.claude-haiku-4-5-20251001-v1:0` via inference profile `eu.anthropic.claude-haiku-4-5-20251001-v1:0`
  - `qwen.qwen3-235b-a22b-2507-v1:0` (on-demand, no profile needed)
- **External access (outside n8n):** manager (`raoof.naushad` IAM user,
  already admin) generated his own AWS access key via the IAM console
  (Security credentials → Create access key) to call these models directly
  from his own machine via `aws bedrock-runtime converse`. No new Terraform
  resource — reuses his existing IAM identity rather than sharing/reusing
  anyone else's credentials.
- If Sonnet 5 access ever clears, re-add it the same way (add to
  `bedrock_models` in `terraform/environments/dev/variables.tf`, `terraform apply`,
  re-run the test script).

### 4. n8n SMTP (forgot-password / invite emails) — done: working on dev and prod

- The mechanism already existed (see `workflows/n8n/docs/infrastructure-overview.md`
  §12): the n8n bootstrap script reads `smtp_*` keys from each
  environment's Secrets Manager secret (`/wusool/dev/n8n`,
  `/wusool/prod/n8n`) and writes them into `/opt/n8n/n8n.env` as
  `N8N_EMAIL_MODE=smtp` + `N8N_SMTP_*`. Only the actual SMTP
  provider/credentials were missing — filled in 2026-08-09.
- **Provider: AWS SES**, region `eu-central-1`, endpoint
  `email-smtp.eu-central-1.amazonaws.com:587`. Chosen over Google
  Workspace/third-party since it stays inside the existing AWS account.
- **Domain verification:** `wusoolcapital.com` verified in SES via 3 DKIM
  CNAME records added to Cloudflare (`*._domainkey.wusoolcapital.com` →
  `*.dkim.amazonses.com`, all `DNS only`). The domain's existing DMARC
  record (`p=quarantine`, pre-existing from Google Workspace) was
  deliberately left untouched — DKIM alignment alone satisfies it, no
  second `_dmarc` record needed.
- **Sandbox mode, not requesting production access** (only 3-4 known
  users need this, not arbitrary recipients) — `tech@wusoolcapital.com`
  individually verified as a recipient identity. The other 3-4 users'
  personal emails still need the same one-time individual verification
  (SES → Identities → Create identity → Email address → they click the
  confirmation link) before *they* can receive reset emails — not done
  yet, not blocking.
- **Credentials:** 2 separate IAM users/SMTP credentials created
  (`wusool-dev-smtp`, `wusool-prod-smtp`) — deliberately not shared
  between environments. Sender identity for both:
  `no-reply@wusoolcapital.com` (no real mailbox — domain verification
  covers any address under it).
- **Secret values were added via the AWS Console, not Terraform** — this
  matches the doc's explicit instruction not to manage these as Terraform
  secret versions or commit them to Git; Terraform only owns the secret
  *container* (`aws_secretsmanager_secret.n8n`), not its value.
- **Gotcha hit and fixed:** `docker compose up -d` does not detect
  changes inside `env_file`-referenced files, so after updating the
  secret and re-running the bootstrap document
  (`wusool-<env>-n8n-bootstrap` via `aws ssm send-command`), the `n8n` and
  `task-runners` containers had to be explicitly force-recreated
  (`docker compose up -d --force-recreate n8n task-runners`) to actually
  pick up the new env file. Verified via
  `docker exec n8n-n8n-1 node -e '...http.get(".../rest/settings")...'` →
  `"smtpSetup":true` on both environments.
- **Second gotcha, prod only — fixed:** re-running the bootstrap document
  also regenerates `/opt/n8n/Caddyfile` from the Terraform template, which
  only knows a single hostname. This silently reverted prod's dual-domain
  Caddy config (from §11.1 — `n8n-prod.wusoolcapital.com` +
  `n8n.wusoolcapital.com` both live) back down to just
  `n8n-prod.wusoolcapital.com`. Re-added both hostnames to one Caddy block
  (`n8n-prod.wusoolcapital.com, n8n.wusoolcapital.com { reverse_proxy
  n8n:5678 ... }`) and restarted the `caddy` container to reapply — both
  domains confirmed working again.
  - **Not yet fixed at the root:** `terraform/modules/n8n-ec2/user_data.sh.tpl`
    still only templates one hostname into the Caddyfile. Any future
    bootstrap re-run on prod (for any reason) will silently break the
    second domain again until this is fixed properly in Terraform, not
    patched live via SSM a third time.
- End-to-end confirmed: real "Reset your n8n password" emails received
  from `Wusool Capital <no-reply@wusoolcapital.com>` for both
  `n8n-dev.wusoolcapital.com` and `n8n-prod.wusoolcapital.com`.

**Resolved 2026-08-10: `n8n-prod.wusoolcapital.com` fully retired.**

- Before removing anything, checked Caddy's access log for real dependency
  (per the open decision from the previous night). Found real, active usage:
  21,320 log lines on the old domain, with the top hits being multiple
  distinct browser sessions (7+ IPs, real Chrome user-agents) actively
  polling `/healthz` — i.e. people had the editor open on the old URL right
  now, not just historical noise. (Some of the volume was self-inflicted
  telemetry noise from n8n's own frontend calling itself via the wrong
  `N8N_HOST`, and some was unrelated bot scanning (`/wp-json/...`) — but the
  `/healthz` browser traffic was real, current usage.)
- Proceeded anyway (explicit decision, accepting the risk to any open
  sessions on the old URL) — fixed `N8N_HOST`/`WEBHOOK_URL` in
  `docker-compose.yml` to `n8n.wusoolcapital.com` only, rewrote the
  Caddyfile to a single-domain block, recreated `n8n`/`task-runners` +
  restarted `caddy`. Verified: `n8n.wusoolcapital.com` works,
  `n8n-prod.wusoolcapital.com` correctly stopped resolving through Caddy.
  Then deleted the `n8n-prod.wusoolcapital.com` A record in Cloudflare.
- **Second bug found and fixed during this same cutover:** rewriting
  `docker-compose.yml` surfaced that the task-runner-launcher fix (see
  §18 gap in `workflows/n8n/docs/infrastructure-overview.md`) was *also* missing —
  same root cause as the Caddyfile issue, confirmed for the first time
  concretely: the registered `wusool-prod-n8n-bootstrap` SSM document runs
  a **stale** embedded script that predates several fixes now present only
  in the local `.tpl` file. Symptom: Python Code nodes failing with
  "Allowed stdlib modules: none" regardless of `N8N_RUNNERS_STDLIB_ALLOW`
  being correctly set — the launcher wasn't loading the custom config file
  at all without `N8N_RUNNERS_CONFIG_PATH` + the volume mount. Re-added
  both live via SSM; confirmed fixed (workflow's Python node ran
  successfully after).
- **Root cause, not yet fixed:** the SSM document itself needs updating to
  match the current template — not just the local file. Until that
  happens, *any* future bootstrap re-run on prod (for any reason) will
  silently revert both the Caddyfile and the task-runner config again.
  Worth prioritizing a proper fix here rather than patching live a third
  time.
- CD pipeline work (developer's auto-deploy-on-push-to-main, hitting a
  308-with-empty-body on large `PUT /api/v1/workflows/*` bodies) is
  separate and still unresolved — waiting on verbose curl output from the
  developer to find the actual redirect cause. Deferred setting up an
  equivalent pipeline for prod until dev's is confirmed working.

### 5. Scribe integration (meetings table + access) — dev networking/role/grants done; prod peering live, real prod credential still pending

- **Done (2026-08-11):** added `database/sql/005_meetings.sql` — canonical
  DDL for the `meetings` table (buyer/seller meeting summaries), owned by
  Wusool but written only by the standalone scribe service (separate
  EC2/Postgres, no shared Alembic chain). See
  [CLIENT_SCHEMA_OVERVIEW.md](../workflows/crm-sync/docs/CLIENT_SCHEMA_OVERVIEW.md#meetings)
  for the column reference.
- Created the least-privilege `scribe_pub` role on `wusool_crm` and granted
  `CONNECT` on the database, `USAGE` on `public`, `SELECT, INSERT, UPDATE` on
  `meetings`, and `SELECT` on `organizations` — scribe needs nothing beyond
  writing its one table and resolving org names to Attio ids.
- **`fk_meetings_org` enabled (2026-08-11):** `meetings.org_id` was
  originally a soft reference (no FK) specifically to survive a race where
  scribe publishes a meeting before its organization has synced from Attio
  into the `wusool_crm` mirror — a hard FK would have rejected that insert
  outright. Enabled the real FK once scribe's publish logic was confirmed to
  check organization existence immediately before insert against the
  Postgres mirror, closing that race. If scribe's publish job starts failing
  on this constraint, that assumption was wrong; revert with
  `ALTER TABLE meetings DROP CONSTRAINT fk_meetings_org;` (also documented
  inline in `005_meetings.sql`).
- **Networking:** added scribe's EC2 security group (`sg-0684b8cf83abfd065`)
  to `allowed_security_group_ids` on `module.postgres` in
  `terraform/environments/dev/main.tf`, applied — scribe can now reach the RDS
  security group across VPCs (peering/connectivity on scribe's side was
  confirmed already in place before this change).
- **Not yet done:** `database/sql/005_meetings.sql`'s `CREATE TYPE`/
  `CREATE TABLE` statements lack the `IF NOT EXISTS` guard every other
  schema file uses — re-running `setup-postgres.ps1` after this one has
  applied once will fail. Fine for the one-time apply already done; needs a
  guard before any future full schema re-run. See
  [database/README.md](../database/README.md#sql-schema-files).
- **Prod networking done (2026-08-17, PR #43):** dev/prod VPCs peered
  specifically so scribe (running in the dev VPC) can reach
  `wusool-prod-postgres` — see `docs/CD_RESTRUCTURE_RESULT.md`/git history
  for the Terraform detail.
- **Not yet done, prod-specific:** `docs/infra_access.md` documents the
  remaining manual step — creating the *real* `scribe_pub` LOGIN role with a
  real generated password on prod (the Alembic chain only ever creates a
  harmless `NOLOGIN` placeholder if the real role doesn't already exist,
  deliberately never a real credential — see that migration's own docstring)
  and handing the resulting DSN to scribe as `WUSOOL_DATABASE_URL_PROD`.
  Until that's done, scribe cannot publish prod meetings even though the
  network path and the table-level grants both exist.

## Keeping this file current

Run the `sync-project-docs` skill after finishing a unit of work (a Terraform
change, a migration milestone, a new workstream). It updates this file's
per-workstream status and re-syncs README files against the actual repo
state — it does not invent progress that isn't reflected in code, docs, or
the migration decision log.
