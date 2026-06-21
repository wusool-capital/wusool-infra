# Wusool Infrastructure

> Current status: the `dev` n8n environment is deployed in Frankfurt
> (`eu-central-1`) with HTTPS, SSM, CloudWatch, SNS, CloudTrail, GuardDuty, and
> Security Hub. See [`environments/dev/README.md`](environments/dev/README.md)
> for the tested operating workflow. Production is a template and has not yet
> been promoted from this validated dev baseline.

Infrastructure-as-Code for the **Wusool** platform, managed with [Terraform](https://www.terraform.io/) on **AWS**.

This repository is the single source of truth for all cloud infrastructure. Every change to the environment — networking, compute, databases, IAM, DNS — flows through Terraform in a pull request and is applied by CI. No manual changes are made in the AWS Console (the console is read-only for humans, except for break-glass scenarios documented below).

---

## Table of Contents

- [Principles](#principles)
- [Repository Structure](#repository-structure)
- [How It Fits Together](#how-it-fits-together)
- [State Management](#state-management)
- [Prerequisites](#prerequisites)
- [One-Time Setup (Bootstrap)](#one-time-setup-bootstrap)
- [Day-to-Day Workflow](#day-to-day-workflow)
- [Adding a New Module](#adding-a-new-module)
- [Adding a New Environment](#adding-a-new-environment)
- [CI/CD Pipeline](#cicd-pipeline)
- [Conventions](#conventions)
- [Break-Glass / Emergency Access](#break-glass--emergency-access)
- [Troubleshooting](#troubleshooting)

---

## Principles

1. **Everything in code.** If it lives in AWS, it lives here. Drift is treated as a bug.
2. **Environments are isolated.** `dev`, `staging`, and `prod` have separate state files, separate AWS accounts (or at minimum separate VPCs/role boundaries), and are promoted in that order.
3. **Modules are reusable; environments are thin.** Reusable logic lives in `modules/`. Each environment is a thin composition that wires modules together with environment-specific inputs.
4. **Remote state, always locked.** State lives in S3 with DynamoDB locking. Local state is never committed.
5. **PR-driven.** `terraform plan` runs on every PR; `terraform apply` runs only after merge to `main`, gated by environment approvals.

---

## Repository Structure

```
wusool-infra/
├── README.md                     # You are here
│
├── environments/                 # One directory per environment — the "live" infra
│   ├── dev/
│   │   ├── backend.tf            # S3 backend config (key = env-specific)
│   │   ├── providers.tf         # AWS provider + region + assume-role config
│   │   ├── main.tf              # Composition: calls modules with dev inputs
│   │   ├── variables.tf        # Input variable declarations
│   │   ├── terraform.tfvars    # dev-specific values (non-secret)
│   │   └── outputs.tf          # Useful outputs (endpoints, ARNs, etc.)
│   ├── staging/
│   │   └── ...                   # Same shape as dev
│   └── prod/
│       └── ...                   # Same shape as dev
│
├── modules/                      # Reusable, environment-agnostic building blocks
│   ├── network/                 # VPC, subnets, NAT, route tables, IGW
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── README.md            # Module-level docs (inputs/outputs/usage)
│   ├── eks/                     # EKS cluster + node groups + IRSA
│   ├── rds/                     # RDS / Aurora PostgreSQL
│   ├── s3/                      # Buckets (app assets, backups, etc.)
│   ├── iam/                     # Roles, policies, OIDC providers
│   ├── ecr/                     # Container registries
│   └── dns/                     # Route53 zones + records
│
├── bootstrap/                    # One-time setup for the Terraform backend itself
│   ├── main.tf                  # Creates the S3 state bucket + DynamoDB lock table
│   ├── variables.tf
│   └── README.md                # See "One-Time Setup" below
│
├── global/                       # Account-wide resources not tied to one environment
│   ├── iam/                     # Org-level roles, GitHub Actions OIDC provider
│   └── route53/                 # Apex/public hosted zones shared across envs
│
├── .github/
│   └── workflows/
│       ├── terraform-plan.yml   # Runs `plan` on PRs, comments the diff
│       └── terraform-apply.yml  # Runs `apply` on merge to main, per-env approval
│
├── scripts/                      # Helper scripts (fmt, validate, lint wrappers)
│   ├── fmt.sh
│   └── validate.sh
│
├── .terraform-version            # Pinned Terraform version (for tfenv)
├── .tflint.hcl                   # TFLint ruleset
├── .gitignore                    # Ignores .terraform/, *.tfstate, secret *.tfvars
└── .pre-commit-config.yaml       # fmt + validate + tflint + tfsec on commit
```

### Why this shape?

- **`environments/` vs `modules/`** is the core split. Modules contain *how* to build something; environments declare *what* to build and *with which values*. This keeps `prod` from accidentally diverging from `dev` in structure while still allowing different sizing.
- **Directory-per-environment** (rather than Terraform workspaces) gives each environment its own backend key, its own provider/role assumption, and a clear, greppable blast radius. A mistake in `dev` cannot touch `prod` state.
- **`bootstrap/` and `global/`** are separated because they have a different lifecycle: they're created once and rarely change, and `bootstrap/` necessarily uses *local* state (it creates the very backend everything else depends on).

---

## How It Fits Together

```
                 ┌─────────────────────────────────────────┐
                 │              modules/                     │
                 │  network · eks · rds · s3 · iam · dns ... │
                 └───────────────▲───────────────▲───────────┘
                                 │ source = ../../modules/...
        ┌────────────────────────┼───────────────┼────────────────────────┐
        │                        │               │                        │
  environments/dev        environments/staging   environments/prod
        │                        │                        │
        ▼                        ▼                        ▼
   s3://…/dev/             s3://…/staging/           s3://…/prod/
   terraform.tfstate       terraform.tfstate         terraform.tfstate
   (DynamoDB lock)         (DynamoDB lock)           (DynamoDB lock)
```

Each environment directory calls the shared modules via relative `source = "../../modules/<name>"` paths and stores its state under an environment-specific key in the shared S3 backend.

---

## State Management

| Concern        | Implementation                                                        |
| -------------- | --------------------------------------------------------------------- |
| Backend        | Amazon S3 (versioned, encrypted with SSE-KMS, public access blocked)  |
| Locking        | Amazon DynamoDB table (`LockID` partition key)                        |
| State key      | `wusool/<environment>/terraform.tfstate`                              |
| Isolation      | One state file per environment — never shared                         |

Example `environments/dev/backend.tf`:

```hcl
terraform {
  backend "s3" {
    bucket         = "wusool-tfstate"
    key            = "wusool/dev/terraform.tfstate"
    region         = "me-central-1"
    dynamodb_table = "wusool-tfstate-locks"
    encrypt        = true
  }
}
```

> The S3 bucket and DynamoDB table themselves are created by `bootstrap/` (see below). This is the classic chicken-and-egg of Terraform backends: bootstrap runs with local state, everything else uses the remote backend it created.

---

## Prerequisites

| Tool            | Version                  | Install                                  |
| --------------- | ------------------------ | ---------------------------------------- |
| Terraform       | see `.terraform-version` | `tfenv install` (recommended)            |
| AWS CLI         | v2                       | `brew install awscli`                    |
| tflint          | latest                   | `brew install tflint`                    |
| tfsec / trivy   | latest                   | `brew install tfsec`                     |
| pre-commit      | latest                   | `brew install pre-commit`                |

AWS access:

- You authenticate with the AWS CLI (SSO recommended). Terraform assumes an environment-specific role; you never use long-lived static keys for `apply`.
- Confirm access before running anything:

```bash
aws sts get-caller-identity
```

---

## One-Time Setup (Bootstrap)

Run **once per AWS account**, by an admin, to create the state backend. After this, no one touches `bootstrap/` again unless the backend itself changes.

```bash
cd bootstrap

# Bootstrap uses LOCAL state on purpose — it is creating the remote backend.
terraform init
terraform plan
terraform apply
```

This provisions:

- The versioned, encrypted S3 bucket (`wusool-tfstate`) for all remote state.
- The DynamoDB lock table (`wusool-tfstate-locks`).
- (Optionally) the GitHub Actions OIDC provider + CI deploy roles, if managed here rather than in `global/iam/`.

Commit the resulting `bootstrap/terraform.tfstate` to a secure location, or migrate it into the bucket it just created. Once the backend exists, every environment can `terraform init` against it.

---

## Day-to-Day Workflow

All changes go through a pull request. Locally:

```bash
# 1. Move into the environment you're changing
cd environments/dev

# 2. Initialize (downloads providers, configures the S3 backend)
terraform init

# 3. Format and validate
terraform fmt -recursive
terraform validate

# 4. See what will change — review this carefully
terraform plan -out=tfplan

# 5. (Optional locally) apply — but normally CI applies on merge
terraform apply tfplan
```

Then:

1. Open a PR. CI runs `fmt`, `validate`, `tflint`, `tfsec`, and `terraform plan` for affected environments, posting the plan as a PR comment.
2. A reviewer approves both the code and the plan output.
3. On merge to `main`, the apply workflow runs `terraform apply` against the environment, gated by a GitHub Environment approval for `staging`/`prod`.
4. Promote the same change `dev → staging → prod`.

---

## Adding a New Module

1. Create `modules/<name>/` with `main.tf`, `variables.tf`, `outputs.tf`, and a `README.md`.
2. Keep it environment-agnostic — no hardcoded account IDs, regions, or environment names. Take everything as input variables.
3. Document inputs/outputs in the module's `README.md`.
4. Reference it from an environment:

```hcl
module "network" {
  source = "../../modules/network"

  environment = "dev"
  cidr_block  = "10.10.0.0/16"
  azs         = ["me-central-1a", "me-central-1b"]
}
```

5. Run `terraform init` in the environment to pick up the new module, then `plan`.

---

## Adding a New Environment

1. Copy an existing environment as a starting point:

   ```bash
   cp -r environments/staging environments/<new-env>
   ```

2. Update `backend.tf` with a new, unique `key` (e.g. `wusool/<new-env>/terraform.tfstate`).
3. Update `terraform.tfvars` with environment-specific values (CIDRs, instance sizes, etc.).
4. Update `providers.tf` if the environment lives in a different AWS account/role.
5. Add the environment to the CI matrix in `.github/workflows/`.
6. `terraform init && terraform plan` to verify before applying.

---

## CI/CD Pipeline

Two GitHub Actions workflows drive automation. CI authenticates to AWS via **OIDC** (no stored AWS keys).

**`terraform-plan.yml`** — on every pull request:
- Detects which environments changed.
- Runs `fmt -check`, `validate`, `tflint`, `tfsec`.
- Runs `terraform plan` and posts the plan as a PR comment.

**`terraform-apply.yml`** — on push to `main`:
- Runs `terraform apply` for the changed environment(s).
- `staging` and `prod` are protected GitHub Environments requiring manual approval before apply proceeds.

---

## Conventions

- **Formatting:** `terraform fmt` is enforced in CI and via pre-commit. PRs that aren't formatted fail.
- **Naming:** resources are prefixed with `wusool-<env>-<purpose>` (e.g. `wusool-prod-app-bucket`).
- **Tagging:** every resource carries `Project = "wusool"`, `Environment`, `ManagedBy = "terraform"`, and `Owner` tags via a shared `default_tags` block in `providers.tf`.
- **Secrets:** never committed. Use AWS Secrets Manager / SSM Parameter Store and reference them via data sources. `*.tfvars` containing secrets are git-ignored; non-secret `terraform.tfvars` may be committed.
- **Versioning:** Terraform and provider versions are pinned (`.terraform-version`, `required_providers`) so plans are reproducible.

---

## Break-Glass / Emergency Access

Manual changes in the AWS Console are forbidden except for genuine incidents. If you must:

1. Make the minimal change required to resolve the incident.
2. Immediately open a PR to codify it in Terraform.
3. Run `terraform plan` to confirm Terraform now shows **no drift** — i.e. the code matches the manual change.

Unreconciled drift is an open incident until closed.

---

## Troubleshooting

| Symptom                                  | Fix                                                                                  |
| ---------------------------------------- | ------------------------------------------------------------------------------------ |
| `Error acquiring the state lock`         | A failed/concurrent run holds the lock. Verify, then `terraform force-unlock <LOCK_ID>`. |
| `Backend configuration changed`          | Run `terraform init -reconfigure`.                                                   |
| Plan shows unexpected diffs              | Likely manual drift — reconcile in code, don't fight it with overrides.              |
| `NoCredentialProviders` / `ExpiredToken` | Re-authenticate: `aws sso login` (or refresh your session), then retry.              |
| Provider/module not found after edit     | Re-run `terraform init` in the environment directory.                                |

---

*Maintained by the Wusool infrastructure team. Questions or changes? Open a PR.*
