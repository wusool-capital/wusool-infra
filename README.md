# Wusool Infrastructure

OpenTofu configuration and application code for the Wusool AWS infrastructure.

> Both `dev` and `prod` are real, deployed environments in one AWS account
> (`030179310793`, `eu-central-1`), applied automatically by GitHub Actions on
> merge to the `dev` or `prod` branch respectively. Neither is a template —
> see [`infrastructure/terraform/README.md`](infrastructure/terraform/README.md)
> for the stack layout and [`CHANGELOG.md`](CHANGELOG.md) for what has changed.

## Architecture

Each service that owns a deployable app or a long-lived EC2 instance gets one
dev instance and one prod instance, built from the same OpenTofu code and
parameterized by environment — not two hand-maintained copies. Today that's:

- **n8n** — Amazon Linux EC2, Docker Compose running Caddy + n8n, HTTPS
  termination in Caddy proxying to n8n on port `5678`, pinned n8n/runners/Caddy
  image digests, an explicitly pinned AMI (no more `most_recent` drift).
- **wusool-toolkit** — one EC2 instance running the Slack bot (see `server/`)
  as a Docker container, deployed by immutable ECR digest (built once in CI,
  never `git clone`+build on the instance). Prod's instance is optional
  (`create_instance` flag) until a real prod rollout is deliberately switched
  on.
- **postgres** — RDS PostgreSQL, dev live, prod provisioned (seeded from a dev
  snapshot, credentials rotated afterward) but not yet the system of record
  for n8n's data plane.

All three sit behind Systems Manager for administration (no SSH by default),
Secrets Manager for environment-specific secrets, CloudWatch logs and alarms,
SNS email notifications, multi-region CloudTrail, and account-wide GuardDuty +
Security Hub.

`scribe` (meeting transcription) and `crm-sync`/`bedrock-ai` (operator
PowerShell scripts with no deployable app of their own) are **not** part of
this per-service dev/prod model yet — see
[`SCRIBE_INFRA_CONTRACT.md`](docs/dev/SCRIBE_INFRA_CONTRACT.md) for scribe's
handover plan.

See:

- [Documentation index](docs/README.md) — user guide, technical docs, handover
- [Changelog](CHANGELOG.md)
- [Terraform stacks/modules/envs layout](infrastructure/terraform/README.md)
- [Slack bot (`server/`) overview](server/README.md)
- [Infrastructure overview](infrastructure/n8n/docs/infrastructure-overview.md)
- [Client schema overview](infrastructure/crm-sync/docs/CLIENT_SCHEMA_OVERVIEW.md) — Attio
  and PostgreSQL overview
- [Contribution and pull-request workflow](CONTRIBUTING.md)
- [Scribe infra contract](docs/dev/SCRIBE_INFRA_CONTRACT.md)
- [Scribe prod DB access runbook](docs/dev/infra_access.md)
- [Slack app setup](docs/dev/SLACK_APP_SETUP.md)

## Repository structure

```text
wusool-infra/
|-- infrastructure/
|   |-- terraform/
|   |   |-- .opentofu-version  # pinned OpenTofu version — this repo uses OpenTofu, not Terraform
|   |   |-- modules/           # HOW each resource is built (reusable, environment-agnostic)
|   |   |   |-- network/           # VPC, subnets, route tables and IGW
|   |   |   |-- n8n-ec2/           # n8n EC2, Caddy, IAM, SSM and monitoring
|   |   |   |-- toolkit-ec2/       # wusool-toolkit EC2 host, Caddy, IAM, SSM and monitoring
|   |   |   |-- bedrock-access/    # IAM policy granting scoped Bedrock model access
|   |   |   `-- postgres-rds/      # RDS PostgreSQL instance
|   |   |-- stacks/            # WHAT to build per service — the roots actually applied
|   |   |   |-- account/           # Account-wide singletons: GuardDuty, Security Hub, OIDC, state bucket
|   |   |   |-- base/              # Per-env VPC, CloudTrail, alerts SNS topic
|   |   |   |-- n8n/               # Per-env n8n stack
|   |   |   |-- toolkit/           # Per-env wusool-toolkit stack + its ECR repo
|   |   |   |-- postgres/          # Per-env RDS stack
|   |   |   `-- peering/           # VPC peering (scribe dev VPC -> wusool-prod-postgres)
|   |   `-- envs/              # dev.tfvars / prod.tfvars — committed, non-secret per-env config
|   |-- n8n/                   # n8n scripts and infrastructure/architecture docs
|   |-- bedrock-ai/            # AWS Bedrock model access scripts (operator PowerShell, no deploy)
|   `-- crm-sync/              # Attio <-> PostgreSQL schema, sync scripts, and docs (operator PowerShell, no deploy)
|-- server/                    # The one deployed Slack bot — modular monolith (FastAPI + Slack Bolt)
|   |-- Dockerfile             # Built once in CI, pushed to ECR, deployed by digest
|   |-- main.py                # The real entrypoint — one AsyncApp, all 5 slash commands
|   |-- alembic/, alembic.ini  # SQLAlchemy schema migrations (schema source of truth)
|   |-- app/models/            # SQLAlchemy models shared across modules
|   |-- app/modules/           # matching_engine, ddl_commands, organizations, attio, notifications, utilities
|   |-- scripts/docs/          # Cross-cutting schema documentation generators
|   `-- scripts/postgres-sync/ # Attio -> PostgreSQL data sync (dev/ and prod/, operator PowerShell)
|-- docs/dev/                  # Handover/contract/runbook docs that aren't tied to one folder's code
`-- .github/                   # workflows/ (CI + OIDC-authenticated CD), actions/ (composite steps) — see below
```

Each stack reads `project`, `environment`, and region-scoped values from
`infrastructure/terraform/envs/<env>.tfvars` — see
[`infrastructure/terraform/README.md`](infrastructure/terraform/README.md) for
the full backend-key and `-var-file` convention, and the collision risk of two
stacks sharing one tfvars file.

## CRM and data-platform schema

Wusool uses Attio and PostgreSQL as connected parts of the same data platform.
Attio is the operational CRM used by the business team. PostgreSQL is the
structured platform layer used for synchronization, enrichment, automation,
analysis, scoring, and generated outputs.

### Platform responsibilities

| Platform | Primary responsibility | Example data |
| --- | --- | --- |
| Attio | Business-facing CRM and workflow management | Organizations, people, deals, mandates, relationship status, and ownership |
| PostgreSQL | Structured storage and machine-processing layer | CRM mirrors, activities, signals, intelligence, matching, documents, events, and synchronization state |
| Shared | Records exchanged between both platforms | Attio identifiers, operational metrics, relationship keys, and selected workflow results |

Core Attio records are mirrored into PostgreSQL using stable Attio record
identifiers. PostgreSQL can then associate CRM records with research,
enrichment, scoring, events, and automation outputs without duplicating their
business identity.

```text
Business users
      |
      v
Attio CRM  <------ selected operational results ------+
      |                                               |
      +------ identifiers and CRM records ------> PostgreSQL
                                                   |
                                                   +--> automation
                                                   +--> enrichment
                                                   +--> analysis and scoring
                                                   `--> documents and reporting
```

### Schema documentation

| Document | Audience | Contents |
| --- | --- | --- |
| [Client schema overview](infrastructure/crm-sync/docs/CLIENT_SCHEMA_OVERVIEW.md) | Clients, management, engineering, and operations | Executive explanation, platform mapping, Attio and PostgreSQL schemas, functional areas, relationships, constraints, and ownership |

### Documented schema scope

The current documentation covers:

- Attio objects and lists for organizations, people, users, buyer roles, seller
  roles, investor/lender roles, deals, and mandates.
- PostgreSQL CRM mirror tables, business-role tables, activities, pipeline
  events, signals, buyer intelligence, seller financials, mandate targets,
  match scores, documents, sector knowledge, relationship graphs, scorecards,
  and Attio synchronization tables.
- Cross-platform mappings, record relationships, ownership boundaries,
  database constraints, and indexes.

### Schema sources of truth

| Schema | Source |
| --- | --- |
| Attio target model | `infrastructure/crm-sync/scripts/dev-attio/config/target-schema.json` |
| Attio migration mapping | `infrastructure/crm-sync/scripts/dev-attio/config/source-to-target-mapping.json` |
| PostgreSQL schema | `server/app/models/` + `server/alembic/versions/` (Alembic migrations, the sole source of truth as of 2026-08-29 — the original flat SQL files that first created this schema were deleted; see git history before that date if you need them). |

The generated documents describe the schema declared in this repository. They
do not prove the current state of a live Attio workspace or PostgreSQL database.
Live validation must be performed separately using the repository validation
scripts.

### Regenerating the documentation

Run the generator from the repository root after changing the Attio model or
PostgreSQL migrations:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File server/scripts/docs/generate-client-schema-overview.ps1
```

Do not manually edit the generated Markdown file; update the schema sources or
generator script and regenerate it instead.

## State backend

Every stack uses a partial S3 backend (`bucket = wusool-tfstate`, region
`me-central-1` — deliberately different from the `eu-central-1` resources —
S3 native lock file, encrypted, versioned) keyed as
`wusool/<env>/<stack>/terraform.tfstate`. `stacks/account` is the one
exception: it has no `-var-file` and its own single state key, since it owns
account-wide singletons. See
[`infrastructure/terraform/README.md`](infrastructure/terraform/README.md) for
the exact `init -backend-config=...` invocation each stack expects.

## Prerequisites

- OpenTofu version from `infrastructure/terraform/.opentofu-version` — this repo uses
  **OpenTofu**, not HashiCorp Terraform; do not run `terraform` against it.
- AWS CLI v2
- Valid AWS credentials or an active AWS SSO session
- An EC2 key pair matching the environment configuration

Verify AWS authentication before planning:

```bash
aws sts get-caller-identity
```

## Development workflow

```bash
cd infrastructure/terraform/stacks/n8n   # or toolkit / postgres / base
tofu init -backend-config="bucket=wusool-tfstate" \
  -backend-config="region=me-central-1" \
  -backend-config="key=wusool/dev/n8n/terraform.tfstate" \
  -backend-config="use_lockfile=true" -backend-config="encrypt=true"
tofu fmt -check
tofu validate
tofu plan -var-file=../../envs/dev.tfvars -out=tfplan
tofu apply tfplan
```

Always review the plan before applying manually. In normal operation you
don't apply by hand at all — merging to `dev` or `prod` triggers the matching
GitHub Actions workflow, which applies whichever stacks actually changed in
dependency order (`base` → `n8n`/`toolkit` → `postgres`) and health-checks
the n8n and toolkit apps before declaring success. See **Continuous
deployment** below.

After deployment:

```bash
tofu output n8n_url
tofu output ssm_command
```

The configured security group allows HTTP and HTTPS. Port `5678` is closed
when `expose_n8n_port = false`, and SSH ingress is omitted when
`ssh_cidr_blocks` is empty. Prefer Systems Manager for shell access.

Dev n8n serves `https://n8n-dev.wusoolcapital.com/`; prod serves
`https://n8n.wusoolcapital.com/`. Cloudflare should keep the matching DNS
record pointed at each environment's EC2 Elastic IP.

## Continuous deployment

`.github/workflows/deploy-dev.yml` and `deploy-prod.yml` trigger on push to
`dev` and `prod` respectively (path-filtered to `infrastructure/terraform/**`
and `server/**`). Each builds the toolkit Docker image and
pushes it to that environment's own ECR repository by immutable digest, then
`_deploy.yml` decides **per stack** whether it actually needs to redeploy:
each of `base`/`n8n`/`toolkit`/`postgres` tracks its own last-deployed commit
in SSM, and only applies (and, for `n8n`/`toolkit`, rolls and health-checks
the app) when a path relevant to that stack changed since then — a
toolkit-only change no longer touches n8n at all. A `base` change, a
workflow/composite-action change, or an `envs/*.tfvars` edit forces every
stack to redeploy regardless, since those can affect (or can't be cheaply
attributed to) more than one stack. See `infrastructure/terraform/README.md`
and the path filters in `.github/workflows/_deploy.yml` for the exact
path-to-stack mapping.

A successful `tofu apply` only proves the bootstrap document was
*registered*, not that the app actually deployed, so neither n8n's nor
toolkit's rollout trusts apply's exit code alone — each re-invokes its SSM
bootstrap document and polls until the app is confirmed serving `/healthz`
(n8n) or `/health` (toolkit) with a `200`. Authentication is GitHub OIDC role
assumption (`wusool-gha-apply-dev` / `wusool-gha-apply-prod`, scoped by
branch in their trust policy) — no static AWS keys. `terraform-plan.yml`
comments a plan on every pull request; `terraform-ci.yml` runs
`fmt`/`validate`; `ci.yml` runs `ruff`/`ty`/`pytest` for the `server/` app
(one project — the root suite plus every module's own suite under
`app/modules/*/tests/`) and PSScriptAnalyzer for the PowerShell scripts.

**Schema changes go through Alembic** — `server/app/models/` +
`server/alembic/`, not numbered flat SQL files (see `server/README.md` and
`server/SCHEMA.md` for the workflow). `server/**` is wired into both deploy
workflows' path filters above, and `_deploy.yml`'s "Run pending database
migrations" step applies `alembic upgrade head` for real against that
environment's actual RDS instance on every `toolkit` redeploy — via SSM
against the toolkit EC2 instance, since RDS is `publicly_accessible = false`
and GitHub Actions has no direct network path to it. This runs *before* the
toolkit app is rolled to its new image, so a failed migration blocks the
deploy rather than leaving new code running against a schema it doesn't have.
`ci.yml`'s `alembic-check` job separately catches drift between models and
migrations on every PR touching `server/**`, against a throwaway Postgres,
before any of that.

The historical flat SQL files (`database/sql/001` through `007`) and the
`setup-postgres.ps1` script that applied them were deleted 2026-08-29 —
Alembic's baseline migrations fully reproduce what they created.
`server/scripts/postgres-sync/dev/sync-postgres.ps1` (Attio data sync, a
separate concern from schema) is unaffected.

## n8n SMTP email

Each environment creates a Secrets Manager secret at
`/${project}/${environment}/n8n`. Add SMTP keys and other sensitive runtime
environment variables to that secret after `tofu apply`; do not put API
keys, webhooks, or SMTP passwords in `terraform.tfvars`.

```powershell
aws secretsmanager put-secret-value `
  --secret-id /wusool/dev/n8n `
  --secret-string '{"smtp_host":"smtp.example.com","smtp_port":587,"smtp_user":"user@example.com","smtp_password":"replace-me","smtp_sender":"Wusool <no-reply@example.com>","smtp_ssl":false,"env":{"GEMINI_API_KEY":"replace-me","SLACK_WEBHOOK_CI":"https://hooks.slack.com/services/replace-me","SLACK_WEBHOOK_ALERTS":"https://hooks.slack.com/services/replace-me"}}'
```

Use `/wusool/prod/n8n` for production. The bootstrap reads the secret and
creates an n8n Docker env file from SMTP settings and any key/value pairs under
the `env` object.

## n8n users

Invite users from n8n's own admin UI (Settings → Users). No repo script does
this today.

Forgot-password works when n8n can send email. Configure the SMTP secret for
the environment, let the SSM bootstrap association rerun, and confirm the n8n
container has `N8N_EMAIL_MODE=smtp` plus the `N8N_SMTP_*` variables.

## Production

Prod is a real, deployed environment — a `10.20.0.0/16` VPC in
`eu-central-1`, its own n8n instance at `https://n8n.wusoolcapital.com/`, and
its own RDS instance seeded from a dev snapshot (credentials rotated off the
snapshot's inherited secret afterward — restoring from a snapshot silently
keeps the source's master credentials otherwise). It is applied exactly the
same way as dev: merge to `prod` deploys it, via
`infrastructure/terraform/envs/prod.tfvars` and the same stacks. The prod
toolkit EC2 instance is live (`create_instance = true` since 2026-08-17);
`stacks/toolkit` still supports `create_instance = false`, which provisions
only the ECR repository and secret.

There is deliberately no human approval gate between a `prod` merge and the
apply — an accepted risk, given every apply is health-checked and
per-stack change detection keeps blast radius small.

## Project status

See [`CHANGELOG.md`](CHANGELOG.md) for what has changed and
[`docs/handover/README.md`](docs/handover/README.md) for the current
delivered state and outstanding items.

## Documentation synchronization

After changing Terraform:

```text
Use $sync-terraform-docs
```

After any other change worth recording — a migration milestone, a new
script, a new workstream, a user-visible bot change — run the sibling skill
to update `CHANGELOG.md`, the `docs/` pages, and the non-Terraform README
files:

```text
Use $sync-project-docs
```

Those phrases are agent instructions, not PowerShell commands. The Terraform
skill compares Terraform with the README files and architecture diagrams,
updates stale documentation, and runs formatting and validation checks.
Neither skill runs `terraform apply`.

## Safety

- Never commit state files, plan files, credentials, private keys, or local
  `terraform.tfvars`.
- Treat Terraform as the source of truth.
- Reconcile emergency console changes back into Terraform immediately.
- A repository review proves declared configuration, not live AWS state.
