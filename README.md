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

- [Infrastructure overview](DOCS/infrastructure-overview.md)
- [Development operating guide](environments/dev/README.md)
- [Contribution and pull-request workflow](CONTRIBUTING.md)

## Repository structure

```text
wusool-infra/
|-- bootstrap/                 # Parameterized backend bootstrap
|-- environments/
|   |-- dev/                   # Frankfurt development composition
|   `-- prod/                  # Production template
|-- modules/
|   |-- network/               # VPC, subnets, route tables and IGW
|   `-- n8n-ec2/               # EC2, n8n, Caddy, IAM, SSM and monitoring
|-- DOCS/                      # Architecture documents and diagrams
|-- scripts/                   # Repository helper scripts
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

## Development state backend

The current development backend is declared in
`environments/dev/backend.tf`.

| Setting | Development value |
| --- | --- |
| Backend | Amazon S3 |
| Region | `eu-central-1` |
| State key | `wusool/dev/terraform.tfstate` |
| Encryption | Enabled |
| Locking | S3 native lock file (`use_lockfile = true`) |
| Bucket protection | Versioning, encryption and public-access blocking |

`bootstrap/` is the one-time backend setup. It is parameterized by region and
bucket name; `bootstrap/terraform.tfvars.example` shows the Frankfurt bucket
used by development. The configuration also declares a DynamoDB lock table for
older backend styles, but the current development backend uses S3 native lock
files instead.

## Prerequisites

- Terraform version from `.terraform-version`
- AWS CLI v2
- Valid AWS credentials or an active AWS SSO session
- An EC2 key pair matching the environment configuration

Verify AWS authentication before planning:

```powershell
aws sts get-caller-identity
```

## Development workflow

```powershell
Set-Location environments/dev
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
`/${project}/${environment}/n8n`. To enable n8n email delivery, add SMTP keys to
that secret after `terraform apply`; do not put the SMTP password in
`terraform.tfvars`.

```powershell
aws secretsmanager put-secret-value `
  --secret-id /wusool/dev/n8n `
  --secret-string '{"smtp_host":"smtp.example.com","smtp_port":587,"smtp_user":"user@example.com","smtp_password":"replace-me","smtp_sender":"Wusool <no-reply@example.com>","smtp_ssl":false}'
```

Use `/wusool/prod/n8n` for production. The bootstrap reads the secret and
creates an n8n Docker env file only when `smtp_host` is present.

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

`environments/prod` is a template using `me-central-1`, a `10.20.0.0/16` VPC,
and larger defaults. Review and reconcile its backend and module inputs before
initialization or deployment. In particular, production still uses the older
DynamoDB backend-locking configuration.

Do not deploy production by changing `TF_VAR_environment` while using the dev
backend. Production must use its own state key, such as
`wusool/prod/terraform.tfstate`.

## Documentation synchronization

After changing Terraform, ask Codex to run the project documentation skill:

```text
Use $sync-terraform-docs
```

That phrase is a Codex instruction, not a PowerShell command. The skill
compares Terraform with the README files and architecture diagrams, updates
stale documentation, and runs formatting and validation checks. It does not run
`terraform apply`.

## Safety

- Never commit state files, plan files, credentials, private keys, or local
  `terraform.tfvars`.
- Treat Terraform as the source of truth.
- Reconcile emergency console changes back into Terraform immediately.
- A repository review proves declared configuration, not live AWS state.
