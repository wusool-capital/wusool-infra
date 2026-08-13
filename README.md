# Wusool Infrastructure

Terraform configuration for the Wusool AWS infrastructure.

> The development configuration declares an n8n environment in Frankfurt
> (`eu-central-1`). Production exists as a separate template and should not be
> treated as deployed or validated from repository contents alone.

## Architecture

The development environment contains:

- VPC `10.10.0.0/16`
- Public subnet `10.10.1.0/24` with an Internet Gateway route
- Reserved private subnet `10.10.2.0/24` with no internet route
- Amazon Linux 2023 EC2 `t3.small` instance with encrypted 30 GiB gp3 storage
- Elastic IP with `n8n-dev.wusoolcapital.com` DNS
- Docker Compose running Caddy and n8n
- HTTPS termination in Caddy, proxying internally to n8n on port `5678`
- AWS Systems Manager for administration and bootstrap
- AWS Secrets Manager secret for environment-specific n8n secrets, including optional SMTP settings
- CloudWatch logs and EC2 status/CPU alarms
- SNS email notifications
- Multi-region CloudTrail with encrypted, versioned S3 log storage
- GuardDuty and Security Hub

See:

- [Infrastructure overview](workflows/n8n/docs/infrastructure-overview.md)
- [Client schema overview](workflows/crm-sync/docs/CLIENT_SCHEMA_OVERVIEW.md) — Attio
  and PostgreSQL overview
- [Development operating guide](terraform/environments/dev/README.md)
- [Contribution and pull-request workflow](CONTRIBUTING.md)

## Repository structure

```text
wusool-infra/
|-- terraform/                 # All Terraform configuration
|   |-- bootstrap/             # Parameterized backend bootstrap
|   |-- environments/
|   |   |-- dev/               # Frankfurt development composition
|   |   `-- prod/              # Production template
|   `-- modules/
|       |-- network/           # VPC, subnets, route tables and IGW
|       `-- n8n-ec2/           # EC2, n8n, Caddy, IAM, SSM and monitoring
|-- database/                  # PostgreSQL migrations, sync, and database tools
|-- workflows/                 # One folder per workflow: scripts + docs together
|   |-- n8n/                   # n8n scripts and infrastructure/architecture docs
|   |-- bedrock-ai/            # AWS Bedrock model access scripts
|   |-- crm-sync/              # Attio <-> PostgreSQL schema, sync scripts, and docs
|   `-- matching-engine/       # Placeholder; the app itself lives in its own repo
|-- scripts/
|   `-- docs/                  # Cross-cutting schema documentation generators
`-- .agents/skills/            # Project-local Codex skills
```

The environment directories compose reusable modules. Each environment has
its own provider, backend, variables and outputs.

Project, environment, and region are Terraform variables. They can be supplied
through `.tfvars` files or `TF_VAR_` environment variables, while each
environment must keep its own backend state key.

```powershell
$env:TF_VAR_project = "wusool"
$env:TF_VAR_environment = "dev"
$env:TF_VAR_aws_region = "eu-central-1"
```

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
| [Client schema overview](workflows/crm-sync/docs/CLIENT_SCHEMA_OVERVIEW.md) | Clients, management, engineering, and operations | Executive explanation, platform mapping, Attio and PostgreSQL schemas, functional areas, relationships, constraints, and ownership |

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
| Attio target model | `workflows/crm-sync/scripts/config/target-schema.json` |
| Attio migration mapping | `workflows/crm-sync/scripts/config/source-to-target-mapping.json` |
| PostgreSQL schema | `database/sql/001_extensions.sql` through `004_machine_layer.sql` |

The generated documents describe the schema declared in this repository. They
do not prove the current state of a live Attio workspace or PostgreSQL database.
Live validation must be performed separately using the repository validation
scripts.

### Regenerating the documentation

Run the generator from the repository root after changing the Attio model or
PostgreSQL migrations:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File scripts/docs/generate-client-schema-overview.ps1
```

Do not manually edit the generated Markdown file; update the schema sources or
generator script and regenerate it instead.

## Development state backend

The current development backend is declared in
`terraform/environments/dev/backend.tf`.

| Setting | Development value |
| --- | --- |
| Backend | Amazon S3 |
| Region | `eu-central-1` |
| State key | `wusool/dev/terraform.tfstate` |
| Encryption | Enabled |
| Locking | S3 native lock file (`use_lockfile = true`) |
| Bucket protection | Versioning, encryption and public-access blocking |

`terraform/bootstrap/` is the one-time backend setup. It is parameterized by region and
bucket name; `terraform/bootstrap/terraform.tfvars.example` shows the Frankfurt bucket
used by development. The configuration also declares a DynamoDB lock table for
older backend styles, but the current development backend uses S3 native lock
files instead.

## Prerequisites

- Terraform version from `terraform/.terraform-version`
- AWS CLI v2
- Valid AWS credentials or an active AWS SSO session
- An EC2 key pair matching the environment configuration

Verify AWS authentication before planning:

```powershell
aws sts get-caller-identity
```

## Development workflow

```powershell
Set-Location terraform/environments/dev
terraform init
terraform fmt -check
terraform validate
terraform plan -out=tfplan
terraform apply tfplan
```

Always review the plan before applying. GitHub Actions checks formatting and
validation for pull requests targeting `dev`; it does not apply infrastructure.

After deployment:

```powershell
terraform output n8n_url
terraform output ssm_command
```

The configured development security group allows HTTP and HTTPS. Port `5678`
is closed when `expose_n8n_port = false`, and SSH ingress is omitted when
`ssh_cidr_blocks` is empty. Prefer Systems Manager for shell access.

Development n8n is configured for `https://n8n-dev.wusoolcapital.com/`.
Cloudflare should keep the `n8n-dev` record pointed at the EC2 Elastic IP.

## n8n SMTP email

Each environment creates a Secrets Manager secret at
`/${project}/${environment}/n8n`. Add SMTP keys and other sensitive runtime
environment variables to that secret after `terraform apply`; do not put API
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

Use the helper script to invite users to development or production:

```powershell
$env:N8N_AUTH_COOKIE = "n8n-auth=..."
.\scripts\invite-n8n-users.ps1 -Environment dev -Email person@example.com
.\scripts\invite-n8n-users.ps1 -Environment prod -EmailFile .\scripts\n8n-users.example.txt
```

Run with `-DryRun` first to confirm the target URL and email list. The script
uses the n8n invite endpoint and accepts either `N8N_AUTH_COOKIE` or
`N8N_API_KEY`; if the API key cannot invite users in the deployed n8n version,
use a browser session cookie from an owner/admin session.

Forgot-password works when n8n can send email. Configure the SMTP secret for
the environment, let the SSM bootstrap association rerun, and confirm the n8n
container has `N8N_EMAIL_MODE=smtp` plus the `N8N_SMTP_*` variables.

## Production

`terraform/environments/prod` is a template using `me-central-1`, a `10.20.0.0/16` VPC,
and larger defaults. Review and reconcile its backend and module inputs before
initialization or deployment. In particular, production still uses the older
DynamoDB backend-locking configuration.

Do not deploy production by changing `TF_VAR_environment` while using the dev
backend. Production must use its own state key, such as
`wusool/prod/terraform.tfstate`.

## Project status

[PROGRESS.md](PROGRESS.md) is the single, high-level file that tracks what
has been done across every workstream (infrastructure, CRM/data-platform
migration, and any new work). Read it before starting a session instead of
reconstructing status from git history.

## Documentation synchronization

After changing Terraform, run the project documentation skill:

```text
Use $sync-terraform-docs
```

After any other change worth recording — a migration milestone, a new script,
a new workstream — run the sibling skill to update `PROGRESS.md` and the
non-Terraform README files:

```text
Use $sync-project-docs
```

Those phrases are agent instructions, not PowerShell commands. The Terraform
skill compares Terraform with the README files and architecture diagrams,
updates stale documentation, and runs formatting and validation checks. Neither
skill runs `terraform apply`.

## Safety

- Never commit state files, plan files, credentials, private keys, or local
  `terraform.tfvars`.
- Treat Terraform as the source of truth.
- Reconcile emergency console changes back into Terraform immediately.
- A repository review proves declared configuration, not live AWS state.
