# Technical Documentation

For developers maintaining `wusool-infra`. This page is the map and the
cross-cutting picture; the deep detail lives in the documents linked from
each section — it is not repeated here.

## System overview

The repository delivers three connected planes:

| Plane | Where | What it is |
| --- | --- | --- |
| **AWS infrastructure** | `infrastructure/terraform/` | OpenTofu per-service stacks for both `dev` and `prod` in one AWS account (`030179310793`, `eu-central-1`). |
| **Slack bot server** | `server/` | One FastAPI + Slack Bolt process (a modular monolith) running the five slash commands. Deployed as a Docker image, pinned by ECR digest, on the `toolkit` EC2 instance. |
| **CRM data platform** | `infrastructure/crm-sync/`, `server/` | Attio (business CRM) kept in sync with the `wusool_crm` PostgreSQL database: a nightly full resync, a real-time webhook, and operator PowerShell scripts. |

n8n (workflow automation) runs on its own EC2 instance per environment and is
infrastructure-managed only — the application is the vendor's.

```text
Slack ──/commands──▶ server (toolkit EC2) ──▶ wusool_crm (RDS PostgreSQL)
                          │        ▲                  ▲
                          ▼        │                  │
                    AWS Bedrock    └── Attio ◀──webhook + nightly resync
                    (matching)
```

## Server modules

`server/app/modules/` — each module is layered `domain → application →
persistence → providers → api`, with Ports (Protocols) at the application
boundary that never expose ORM types. Architecture fitness tests
(`tests/test_architecture.py`, per module and repo-wide) enforce this.

New to this pattern? [`../dev/MODULAR_MONOLITH_GUIDE.md`](../dev/MODULAR_MONOLITH_GUIDE.md)
explains the mental model and walks through reading a module end to end.

| Module | Responsibility |
| --- | --- |
| `matching_engine` | `/find-match` — requirement extraction, filtering, scoring, reasoning, persistence, Slack delivery. |
| `ddl_commands` | `/edit-seller`, `/edit-buyer`, `/add-seller`, `/add-buyer`, and the inbound Attio webhook + nightly resync job. |
| `organizations` | Shared `Organization` search and persistence (used by both command modules). |
| `attio` | Attio vendor client, webhook payload types, value extraction. |
| `notifications` | Cross-module Slack notifier Port and Slack `mrkdwn` text handling. |
| `utilities` | Cross-cutting infra: logging, retry, `Money`, database wiring, shared Slack Bolt app construction. |

`server/main.py` is the one deployed entrypoint: it builds a single Slack
`AsyncApp`, registers both command modules' handlers, and serves one
`POST /slack/events`. Each module's `bootstrap.py::create_app()` is for
standalone testing only.

See [`server/README.md`](../../server/README.md) and each module's own
`README.md`.

## Data model

- **Source of truth:** SQLAlchemy models in `server/app/models/`, Alembic
  migrations in `server/alembic/`. The server never creates tables at
  runtime; schema changes go through a migration reviewed by the data
  engineer.
- **Reference:** [`server/SCHEMA.md`](../../server/SCHEMA.md) (Postgres
  schema) and
  [`infrastructure/crm-sync/docs/CLIENT_SCHEMA_OVERVIEW.md`](../../infrastructure/crm-sync/docs/CLIENT_SCHEMA_OVERVIEW.md)
  (Attio + Postgres, cross-platform mapping).
- CI's `alembic-check` job fails any PR whose models and migrations disagree.

## AI / LLM architecture

Only `matching_engine` uses an LLM, via AWS Bedrock:

1. **Extraction call** (Claude Haiku 4.5) — buyer fields + free text + recent
   meeting notes → structured hard requirements and soft preferences.
2. **Deterministic filtering and scoring** — a fixed criterion registry; a
   candidate is dropped only on a *confirmed* hard-requirement failure.
   Missing data never eliminates anyone. Score is a weighted average;
   `data_confidence` is tracked separately and never folded into the rank.
3. **Reasoning call** (Claude Sonnet 4.6) — narrative for the top-N shortlist
   only. It cannot change scores or introduce facts not passed to it.

Models are provisioned in Terraform (`dev.tfvars` `bedrock_models`) and
reached through cross-region inference profiles. Full pipeline:
[`server/app/modules/matching_engine/README.md`](../../server/app/modules/matching_engine/README.md).

## Authentication and authorization

| Boundary | Mechanism |
| --- | --- |
| Slack → server | Bolt verifies every request's signature against the Slack signing secret. |
| Attio → server webhook | HMAC signature check using `ATTIO_WEBHOOK_SECRET`. |
| GitHub Actions → AWS | OIDC role assumption (`wusool-gha-apply-dev` / `-prod`, branch-scoped in the trust policy). No static AWS keys. |
| Server → AWS (Bedrock, etc.) | The EC2 instance role / task role. Static keys are for local dev only. |
| Server → database | Credentials from Secrets Manager. |
| End users → bot commands | **None.** Any workspace member can run any command. |

## External services

AWS (EC2, RDS PostgreSQL, Bedrock, ECR, Secrets Manager, Systems Manager,
CloudWatch, SNS, CloudTrail, GuardDuty, Security Hub, SES), Attio, Slack,
Cloudflare (DNS), GitHub Actions, Firecrawl (optional web-lead fallback in
matching), n8n.

## Deployment

Merging to `dev` or `prod` triggers `deploy-dev.yml` / `deploy-prod.yml`
(path-filtered to `infrastructure/terraform/**` and `server/**`):

1. Build the toolkit Docker image, push to that environment's ECR repo by
   immutable digest.
2. `_deploy.yml` decides **per stack** whether to redeploy — each of
   `base` / `n8n` / `toolkit` / `postgres` tracks its own last-deployed
   commit in SSM and only applies when a relevant path changed. `base`,
   composite-action, or `envs/*.tfvars` changes force all stacks.
3. Apply changed stacks in dependency order (`base` → `n8n` / `toolkit` →
   `postgres`).
4. On a `toolkit` redeploy, run `alembic upgrade head` against that
   environment's RDS **via SSM** (RDS is not publicly reachable), *before*
   rolling the app — a failed migration blocks the deploy.
5. Re-invoke the SSM bootstrap document and poll until the app serves
   `/healthz` (n8n) or `/health` (toolkit) with `200`. `tofu apply`'s exit
   code alone is not trusted.

There is deliberately no manual approval gate before a `prod` apply — an
accepted risk, given every apply is health-checked and per-stack change
detection keeps the blast radius small.

State: every stack uses a partial S3 backend (`bucket = wusool-tfstate`,
`me-central-1`, native lock file) keyed `wusool/<env>/<stack>/terraform.tfstate`.
`stacks/account` is the exception (no `-var-file`, single key).

## CI

| Workflow | Runs |
| --- | --- |
| `ci.yml` | `ruff`, `ty`, `pytest` for `server/` (root suite + per-module suites); `alembic-check` (model/migration drift against a throwaway Postgres); PSScriptAnalyzer for PowerShell. |
| `terraform-ci.yml` | `tofu fmt -check` and `tofu validate` per stack. |
| `terraform-plan.yml` | Comments a plan on every PR. |
| `nightly-attio-sync.yml` | Nightly Attio → Postgres full resync via SSM. |

## Configuration

- Local: `server/.env`, copied from `server/.env.example`.
  `tests/test_env_example.py` fails if the example drifts from any module's
  `Settings`.
- Runtime secrets: AWS Secrets Manager, `/wusool/<env>/n8n` and
  `/wusool/<env>/toolkit`. Never in `*.tfvars` or Git.
- Committed per-environment config: `infrastructure/terraform/envs/{dev,prod}.tfvars`.

## Key business rules

- **Attio-first writes.** `/edit-*` and `/add-*` write to DEV Attio before
  Postgres, so the scheduled resync converges instead of clobbering the
  change. Partial-write failures report exactly what landed.
- **Schema authority is the data engineer**, not the bot — see the "History"
  section of
  [`ddl_commands/README.md`](../../server/app/modules/ddl_commands/README.md).
- **Not every column is Slack-editable** — see that README's "Excluded
  fields".

## Document map

| Topic | Document |
| --- | --- |
| Repo layout, CD, schema pipeline | [`README.md`](../../README.md) |
| Terraform stacks / modules / backend keys | [`infrastructure/terraform/README.md`](../../infrastructure/terraform/README.md) |
| Slack bot process | [`server/README.md`](../../server/README.md) + module READMEs |
| Postgres schema | [`server/SCHEMA.md`](../../server/SCHEMA.md) |
| Attio + Postgres schema, cross-platform mapping | [`infrastructure/crm-sync/docs/CLIENT_SCHEMA_OVERVIEW.md`](../../infrastructure/crm-sync/docs/CLIENT_SCHEMA_OVERVIEW.md) |
| n8n infrastructure detail | [`infrastructure/n8n/docs/infrastructure-overview.md`](../../infrastructure/n8n/docs/infrastructure-overview.md) *(predates both repo restructures — its structure/path sections are stale; the n8n behaviour detail is still accurate)* |
| Change history | [`CHANGELOG.md`](../../CHANGELOG.md) |
| Scribe infra handover | [`docs/dev/SCRIBE_INFRA_CONTRACT.md`](../dev/SCRIBE_INFRA_CONTRACT.md) |
| Slack app setup | [`docs/dev/SLACK_APP_SETUP.md`](../dev/SLACK_APP_SETUP.md) |
| Contribution / PR workflow | [`CONTRIBUTING.md`](../../CONTRIBUTING.md) |
