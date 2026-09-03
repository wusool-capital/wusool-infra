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
| Attio | Business CRM of record; matching source data | Wusool Attio (DEV + SOURCE workspaces) |
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
| CRM migration | Investor/lender scope; scorecards scope; final owner/advisor backfill (currently `tech@wusoolcapital.com` as an approved stopgap); re-run the PostgreSQL sync against DEV Attio's current state and complete the Attio ↔ Postgres reconciliation audit. |
| Scribe (prod) | Create the real `scribe_pub` LOGIN role with a generated password on prod and hand the DSN to scribe as `WUSOOL_DATABASE_URL_PROD`. Until then scribe cannot publish prod meetings. |
| n8n | Update the registered prod `wusool-prod-n8n-bootstrap` SSM document to match the current template so re-runs stop reverting live fixes. |
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
