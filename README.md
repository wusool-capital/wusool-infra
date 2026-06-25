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
- Elastic IP and an IP-derived `sslip.io` hostname
- Docker Compose running Caddy and n8n
- HTTPS termination in Caddy, proxying internally to n8n on port `5678`
- AWS Systems Manager for administration and bootstrap
- CloudWatch logs and EC2 status/CPU alarms
- SNS email notifications
- Multi-region CloudTrail with encrypted, versioned S3 log storage
- GuardDuty and Security Hub

See:

- [Development architecture](DOCS/dev-infrastructure-architecture.md)
- [Markdown network diagram](DOCS/wusool-dev-network-diagram.md)
- [Development operating guide](environments/dev/README.md)
- [Contribution and pull-request workflow](CONTRIBUTING.md)

## Repository structure

```text
wusool-infra/
├── bootstrap/                 # Parameterized S3 backend and legacy lock table
├── bootstrap-frankfurt/       # Frankfurt S3 backend used by dev
├── environments/
│   ├── dev/                   # Frankfurt development composition
│   └── prod/                  # Production template
├── modules/
│   ├── network/               # VPC, subnets, route tables and IGW
│   └── n8n-ec2/               # EC2, n8n, Caddy, IAM, SSM and monitoring
├── DOCS/                      # Architecture documents and diagrams
├── scripts/                   # Documentation helper scripts
└── .agents/skills/            # Project-local Codex skills
```

The environment directories compose reusable modules. Each environment has
its own provider, backend, variables and outputs.

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

`bootstrap-frankfurt/` creates the S3 bucket used by this backend. The
parameterized `bootstrap/` configuration also declares a DynamoDB lock table,
but the current development backend does not use it.

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

## Production

`environments/prod` is a template using `me-central-1`, a `10.20.0.0/16` VPC,
and larger defaults. Review and reconcile its backend and module inputs before
initialization or deployment. In particular, production still uses the older
DynamoDB backend-locking configuration.

## Documentation synchronization

After changing Terraform, invoke the project skill:

```text
Use $sync-terraform-docs
```

It compares Terraform with the README files and architecture diagrams, updates
stale documentation, and runs formatting and validation checks. It does not
run `terraform apply`.

## Safety

- Never commit state files, plan files, credentials, private keys, or local
  `terraform.tfvars`.
- Treat Terraform as the source of truth.
- Reconcile emergency console changes back into Terraform immediately.
- A repository review proves declared configuration, not live AWS state.
