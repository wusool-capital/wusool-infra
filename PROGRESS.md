# Project Progress

Single entry point for "what has been done so far" across every workstream in
this repository. Read this file first in a new session before digging through
git history or chat logs. Detailed, granular status for each workstream lives
in its own document (linked below) — this file stays a short, high-level
index and is kept current by the `sync-project-docs` skill (or manually,
see [Keeping this file current](#keeping-this-file-current)).

Last updated: 2026-08-09

## Workstreams

### 1. Infrastructure (Terraform / n8n) — dev deployed via Terraform; prod is live but Terraform-orphaned

- Development environment (`environments/dev`) is declared and deployable:
  VPC, EC2 n8n host behind Caddy/HTTPS, Secrets Manager, CloudWatch alarms,
  SNS, multi-region CloudTrail, GuardDuty, Security Hub. See
  [README.md](README.md#architecture) and
  [DOCS/n8n/infrastructure-overview.md](DOCS/n8n/infrastructure-overview.md).
- **Correction (2026-08-08):** production is actually deployed and running
  (`wusool-prod-n8n`, `i-0087f9ecb02462b2e`) — but in `eu-central-1`
  alongside dev, not `me-central-1` as `environments/prod`'s Terraform
  config declares. That config is not what created the real prod instance;
  `terraform apply` there would not affect it. See
  [DOCS/n8n/infrastructure-overview.md](DOCS/n8n/infrastructure-overview.md)
  section 18, "Known Infrastructure Gaps," for details and the workaround
  (direct SSM changes to prod until this is reconciled).
- Fixed a real n8n default-config bug (2026-08-08): the external Python task
  runner's launcher config ships with `N8N_RUNNERS_STDLIB_ALLOW` forced blank
  regardless of environment variables, breaking all stdlib imports (e.g.
  `datetime`) in Python Code nodes on n8n `2.27.5`. Fixed via a custom
  launcher config file + `N8N_RUNNERS_CONFIG_PATH`, applied live to prod and
  added to the `modules/n8n-ec2` Terraform template for future deployments;
  not yet applied to dev (not known to be needed there) — see
  infrastructure-overview.md section 9.1.
- Documentation is kept in sync with actual Terraform via the
  `sync-terraform-docs` skill (see `.agents/skills/sync-terraform-docs/`).
- **Done (2026-08-09):** renamed prod's public n8n domain from
  `n8n-prod.wusoolcapital.com` to `n8n.wusoolcapital.com` using a dual-domain
  approach — both domains stay live simultaneously, so existing
  workflows/webhook URLs never broke. Applied directly on
  `wusool-prod-n8n` (`i-0087f9ecb02462b2e`) via SSM: (1) added a Cloudflare
  `A` record for `n8n.wusoolcapital.com` (zone lives under the `Jules@`
  Cloudflare account, not `Tech@`) pointing at the same IP as `n8n-prod`,
  DNS-only/grey-cloud to match; (2) `/opt/n8n/Caddyfile` now lists both
  hostnames in one site block (`n8n-prod.wusoolcapital.com,
  n8n.wusoolcapital.com { reverse_proxy n8n:5678 ... }`); (3)
  `/opt/n8n/docker-compose.yml`'s `N8N_HOST`/`WEBHOOK_URL` now point at
  `n8n.wusoolcapital.com` (only affects newly generated webhook/OAuth URLs
  going forward — existing ones keep working on both domains since n8n's
  webhook routing is path-based, not Host-header-validated); (4) `docker
  compose up -d` recreated the `n8n`/`task-runners` containers (env changed)
  and `docker compose restart caddy` picked up the new Caddyfile (Compose
  does not auto-recreate a container just because a bind-mounted file's
  contents changed). Verified both `https://n8n-prod.wusoolcapital.com` and
  `https://n8n.wusoolcapital.com` return `HTTP/2 200` with valid Caddy-issued
  TLS. `Caddyfile.bak`/`docker-compose.yml.bak` left on the box from before
  the change. **Not yet done:** mirroring this into the
  `modules/n8n-ec2` Terraform template (prod is Terraform-orphaned per the
  gap above, so the live box isn't affected either way, but the template
  should reflect the same dual-domain pattern for future deployments/dev).

### 2. CRM / data-platform migration (Attio + PostgreSQL) — core objects migrated and re-synced, tail work remains

High-level summary only — the authoritative, field-by-field decision log is
maintained separately as local assistant working memory (not part of this
repo) per `AGENTS.md`; consult that when doing further Attio/Postgres work.

**Done:**
- Organization, Person, Buyer Role, Seller Role, Mandates, and Deal objects
  migrated SOURCE Attio → DEV Attio, idempotent by `legacy_attio_id`.
- Added `scripts/attio/sync-all.ps1` (2026-08-08/09): single entry point for
  a full migration run, wrapping the existing `sync-objects.ps1`/
  `sync-lists.ps1` in the required dependency order (`organizations ->
  person -> buyer_role -> seller_role -> deals -> mandates`), fails fast on
  the first error, supports running a subset by name, and parallel workers
  where the underlying scripts support it. See
  [scripts/attio/README.md](scripts/attio/README.md).
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
  [CRM_MIGRATION_GUIDE.md](DOCS/migration/CRM_MIGRATION_GUIDE.md) and
  [CLIENT_SCHEMA_OVERVIEW.md](DOCS/migration/CLIENT_SCHEMA_OVERVIEW.md)).

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
  `modules/bedrock-access` Terraform module grants the existing n8n EC2
  instance role (`wusool-dev-n8n-ec2`) `bedrock:InvokeModel`/
  `InvokeModelWithResponseStream` on specific foundation models, wired into
  `environments/dev`. See `modules/bedrock-access/` and
  `environments/dev/variables.tf` (`bedrock_models`).
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
  PASS via `scripts/aws/test-bedrock-models.ps1`:**
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
  `bedrock_models` in `environments/dev/variables.tf`, `terraform apply`,
  re-run the test script).

### 4. n8n SMTP (forgot-password / invite emails) — done: working on dev and prod

- The mechanism already existed (see `DOCS/n8n/infrastructure-overview.md`
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
  - **Not yet fixed at the root:** `modules/n8n-ec2/user_data.sh.tpl`
    still only templates one hostname into the Caddyfile. Any future
    bootstrap re-run on prod (for any reason) will silently break the
    second domain again until this is fixed properly in Terraform, not
    patched live via SSM a third time.
- End-to-end confirmed: real "Reset your n8n password" emails received
  from `Wusool Capital <no-reply@wusoolcapital.com>` for both
  `n8n-dev.wusoolcapital.com` and `n8n-prod.wusoolcapital.com`.

**Open decision, paused 2026-08-09 evening — pick up here:** whether/when
to fully retire `n8n-prod.wusoolcapital.com` in favor of
`n8n.wusoolcapital.com` alone. Two options discussed, neither actioned yet:

- **Option A — do it now:** flip `N8N_HOST`/`WEBHOOK_URL` to the new domain
  only and delete the old DNS record. Fast (~15 min), but risky —
  checking Caddy's access log for only an hour or so beforehand does
  **not** prove nothing external depends on the old URL (an infrequent
  partner webhook or OAuth redirect would not show up in a short log
  window and would break silently later).
- **Option B (leaning this way) — defer the risky half:** switch n8n's own
  *generated* links to the new domain now, but leave the old domain's DNS
  record alive as a no-cost safety net for longer (check
  `docker compose logs caddy` / `/data/access.log` on `wusool-prod-n8n`
  periodically for any continued hits to `n8n-prod.wusoolcapital.com`
  before actually removing it).

No changes made yet either way — both domains are still live and working
as of this note.

## Keeping this file current

Run the `sync-project-docs` skill after finishing a unit of work (a Terraform
change, a migration milestone, a new workstream). It updates this file's
per-workstream status and re-syncs README files against the actual repo
state — it does not invent progress that isn't reflected in code, docs, or
the migration decision log.
