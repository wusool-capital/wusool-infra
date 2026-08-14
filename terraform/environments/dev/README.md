# Development environment

See the [infrastructure overview](../../../workflows/n8n/docs/infrastructure-overview.md) for
diagrams of the deployed AWS resources, request path, and operational controls.

The development Terraform configuration declares n8n on an Amazon Linux EC2
instance in Frankfurt (`eu-central-1`). Terraform state is stored remotely in
the S3 backend declared in `backend.tf`.

## Architecture

- VPC with public and private subnets
- EC2 with an encrypted root volume and Elastic IP
- Docker Compose running n8n and Caddy
- HTTPS through `n8n-dev.wusoolcapital.com`
- Port 5678 closed publicly; Caddy proxies HTTPS traffic to n8n internally
- EC2 IAM role for Systems Manager and CloudWatch Agent
- Secrets Manager secret `/wusool/dev/n8n` for environment-specific n8n secrets
- No public SSH ingress; administrators connect through Systems Manager
- CloudWatch logs, instance health alarm, and high-CPU alarm
- SNS email notifications
- CloudTrail with a private, encrypted, versioned S3 bucket
- GuardDuty and Security Hub

## Local configuration

Copy the example and fill in local values. The resulting file is ignored by
Git and must not be committed.

```powershell
Copy-Item terraform.tfvars.example terraform.tfvars
```

Local values include the EC2 key-pair name and optional alert email address.
An administrator CIDR is required only when SSH ingress is intentionally
enabled; the supplied configuration uses Systems Manager and an empty SSH
CIDR list. The supplied `n8n_webhook_url` is
`https://n8n-dev.wusoolcapital.com/`; keep the Cloudflare `n8n-dev` DNS record
pointed at the EC2 Elastic IP.

The project, environment, and region can also be supplied as environment
variables for demos or automation:

```powershell
$env:TF_VAR_project = "wusool"
$env:TF_VAR_environment = "dev"
$env:TF_VAR_aws_region = "eu-central-1"
```

Keep dev and prod on separate Terraform backend state keys.

## Workflow

```powershell
terraform init
terraform fmt -check
terraform validate
terraform plan -out=tfplan
terraform apply tfplan
```

After apply, use `terraform output n8n_url` for the HTTPS endpoint. Confirm the
SNS subscription email before expecting alerts. Use the `ssm_command` output
for shell access without exposing SSH more broadly.

Use `terraform output n8n_secret_name` to get the Secrets Manager secret name.
Add or rotate secret values with AWS CLI or the AWS console after apply; do not
store secret values in `terraform.tfvars`.

For SMTP email, store these optional JSON keys in the n8n secret:

```json
{
  "smtp_host": "smtp.example.com",
  "smtp_port": 587,
  "smtp_user": "user@example.com",
  "smtp_password": "replace-me",
  "smtp_sender": "Wusool <no-reply@example.com>",
  "smtp_ssl": false,
  "env": {
    "GEMINI_API_KEY": "replace-me",
    "SLACK_WEBHOOK_CI": "https://hooks.slack.com/services/replace-me",
    "SLACK_WEBHOOK_ALERTS": "https://hooks.slack.com/services/replace-me"
  }
}
```

The EC2 bootstrap reads `/wusool/dev/n8n`, writes `/opt/n8n/n8n.env`, and passes
the SMTP values to n8n as `N8N_SMTP_*` environment variables. Key/value pairs
under `env` are also written to the n8n env file. Repeat the same shape in
`/wusool/prod/n8n` for production.

## User invites and password resets

Invite one or more users with:

```powershell
$env:N8N_AUTH_COOKIE = "n8n-auth=..."
..\..\scripts\invite-n8n-users.ps1 -Environment dev -Email person@example.com
```

For bulk invites, copy `../../../scripts/n8n-users.example.txt`, replace the
placeholder addresses, and pass it with `-EmailFile`. Add `-DryRun` to verify
the target before sending.

Forgot-password is handled by n8n once SMTP is configured. If reset emails do
not arrive, check the SMTP secret, rerun the bootstrap association, and inspect
`/opt/n8n/n8n.env` on the instance through Systems Manager.

Never commit `.terraform/`, `tfplan`, `terraform.tfvars`, state files, private
keys, or AWS credentials.

## Matching-engine (Buyer-Seller Matching bot)

A second, separate EC2 instance (`terraform/modules/matching-engine-ec2`)
runs the Slack-connected matching-engine app from
`workflows/matching-engine`, on a `t2.micro` (AWS Free Tier eligible). It
reuses this environment's VPC/public subnet and the existing shared RDS
Postgres instance (`module.postgres`) — it does not run its own database.

Deploy flow, on `terraform apply`:

1. The instance boots, installs Docker/Docker Compose/CloudWatch Agent.
2. It reads `/wusool/dev/matching-engine` from Secrets Manager and clones
   `matching_engine_git_repo_url` at `matching_engine_git_ref` using a
   short-lived, embedded GitHub token (never persisted to `.git/config`).
3. It writes the app's `.env.production` from the secret, builds the image
   from `workflows/matching-engine/Dockerfile`, and starts it behind Caddy
   (HTTPS, same sslip.io/Elastic-IP pattern as n8n unless
   `matching_engine_public_url` is set to a real domain).

Populate the secret before (or right after) the first apply:

```json
{
  "slack_bot_token": "xoxb-...",
  "slack_signing_secret": "...",
  "database_url": "postgresql://<app_db_user>:<password>@<rds-endpoint>:5432/wusool_crm",
  "github_token": "github_pat_...-with-read-only-access-to-the-repo",
  "env": {
    "AWS_BEDROCK_MODEL_ID_EXTRACTION": "eu.anthropic.claude-haiku-4-5-20251001-v1:0",
    "AWS_BEDROCK_MODEL_ID_REASONING": "eu.anthropic.claude-sonnet-4-6",
    "FIRECRAWL_API_KEY": "fc-... (optional — omit to disable the Google-Maps web-fallback feature entirely; the app logs a warning at startup if this is unset)",
    "WEB_FALLBACK_MIN_SCORE": "50.0",
    "MEETING_NOTES_MAX_CHARS": "600",
    "MEETING_NOTES_MAX_TOTAL_CHARS": "4000",
    "ENABLE_SELLER_MEETING_NOTES": "false"
  }
}
```

`database_url` must point at a Postgres role scoped to `wusool_crm` (not the
RDS master user) — create that role once via the existing
`scripts/db/sql/*.sql` tooling, same as any other CRM consumer.

After apply:

- `terraform output matching_engine_url` — set this as the Slack app's
  Events API / interactivity Request URL, both ending in `/slack/events`.
- `terraform output matching_engine_ssm_command` — shell access without SSH.
- `terraform output matching_engine_redeploy_command` — re-run the bootstrap
  (git pull, rebuild, restart) on the existing instance without replacing it,
  e.g. after pushing a new commit to `matching_engine_git_ref`.
- `terraform output matching_engine_secret_name` — the Secrets Manager
  secret name for the JSON above.

The instance's IAM role is also granted Bedrock `InvokeModel` access via a
second `bedrock-access` module instance, using the same `bedrock_models`
variable as n8n.
