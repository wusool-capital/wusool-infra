# Development environment

See the [infrastructure overview](../../DOCS/infrastructure-overview.md) for
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

For bulk invites, copy `../../scripts/n8n-users.example.txt`, replace the
placeholder addresses, and pass it with `-EmailFile`. Add `-DryRun` to verify
the target before sending.

Forgot-password is handled by n8n once SMTP is configured. If reset emails do
not arrive, check the SMTP secret, rerun the bootstrap association, and inspect
`/opt/n8n/n8n.env` on the instance through Systems Manager.

Never commit `.terraform/`, `tfplan`, `terraform.tfvars`, state files, private
keys, or AWS credentials.
