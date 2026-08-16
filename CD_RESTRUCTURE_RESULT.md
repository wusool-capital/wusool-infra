# CD Restructure — Result

What this branch (`plan-cd-restructure` → `dev`, PR #26) actually changed and
enforces, as verified against live AWS (`030179310793`, `eu-central-1`), not
as originally planned. See [`Final_restructure_plan.md`](Final_restructure_plan.md)
for the original design and [`RESTRUCTURE_PROGRESS.md`](RESTRUCTURE_PROGRESS.md)
for the full phase-by-phase log with verification evidence for every step.

## Before → after

| | Before | After |
|---|---|---|
| Terraform layout | Two hand-maintained env directories (`terraform/environments/{dev,prod}`), already drifted from each other | One `terraform/stacks/{account,base,n8n,toolkit,postgres}` per service, parameterized by `terraform/envs/{dev,prod}.tfvars` |
| Tool | Ambiguous — lockfiles referenced Terraform, only OpenTofu was installed | Standardized on **OpenTofu**, version-pinned via `terraform/.opentofu-version` |
| CD | **None.** Only `terraform-ci.yml` existed (`fmt` + `validate -backend=false`); nothing ever deployed | `deploy-dev.yml` / `deploy-prod.yml` apply on every merge to `dev` / `main`, fully verified (SSM bootstrap polled to `Success`, `/health` checked for `200`) |
| Auth | N/A (no CD) | GitHub OIDC role assumption — **no static AWS keys anywhere** |
| App deploy | `git clone` + `docker compose build` on the live EC2 instance | Build once in CI, push to ECR, deploy by immutable `sha256:` digest — dev and prod run bit-identical artifacts |
| AMI | `data "aws_ami" { most_recent = true }` + `ignore_changes = [ami]` — silently froze instances with no reviewable diff | Explicit `ami_id` variable, pinned to each instance's currently-running AMI |
| Prod database | Did not exist | RDS provisioned, seeded from a dev snapshot, credentials rotated off the inherited snapshot secret |
| Branches | `main` (default) + `dev`, app/data drifted between them | `dev` is the only active branch; `main` retired (tagged `archive/main-pre-restructure`, deleted) |
| Repo review | No `CODEOWNERS` | `.github/CODEOWNERS` — infra changes require review from `@sinanshamsudheen` + `@raoofnaushad` |
| Orphan AWS resources | Two empty `me-central-1` VPCs (`n8n-dev-vpc`, `n8n-prod-vpc`), never used, in no state file | Deleted |
| App test coverage | Nothing ran in CI | `ci.yml`: `ruff`/`ty`/`pytest` for the Python app, PSScriptAnalyzer for the PowerShell scripts |

## Terraform structure

```
terraform/
  .opentofu-version   # pinned OpenTofu version — this repo uses OpenTofu, not HashiCorp Terraform
  modules/             # reusable "how" — never applied directly, no backend
    network/               # VPC, subnets, route tables, IGW
    n8n-ec2/                # n8n EC2, Caddy, IAM, SSM, monitoring
    toolkit-ec2/             # wusool-toolkit EC2 host, Caddy, IAM, SSM, monitoring
    bedrock-access/          # IAM policy for scoped Bedrock model access
    postgres-rds/            # RDS PostgreSQL instance
  stacks/              # per-service "what" — the roots actually applied
    account/                # applied ONCE, no -var-file: GuardDuty, Security Hub, OIDC provider + roles, state bucket
    base/                    # per-env: VPC, CloudTrail, alerts SNS topic
    n8n/                     # per-env: n8n EC2 + secret + optional Bedrock access
    toolkit/                 # per-env: wusool-toolkit EC2 + its own ECR repo + secret
    postgres/                # per-env: RDS instance
  envs/
    dev.tfvars           # committed, non-secret per-env config
    prod.tfvars          # committed, non-secret per-env config
```

`terraform/environments/` and `terraform/bootstrap/` are deleted — every
resource was migrated with `state mv` (pull → per-resource move → push to
both the new and old backend → verify `0 to add / 0 to change / 0 to destroy`
on both sides before continuing), never recreated. State history and
SecurityHub finding history were preserved, not reset.

Each stack has its own S3 backend key: `wusool/<env>/<stack>/terraform.tfstate`,
bucket `wusool-tfstate` (region `me-central-1`, deliberately different from
the `eu-central-1` resources), S3 native lock file, encrypted, versioned.
`stacks/account` is the one exception — single state key, no `-var-file`,
since it owns account-wide singletons (GuardDuty and SecurityHub are
one-per-account-per-region; a per-env stack would fail applying prod's
tfvars against them).

**Enforced convention, not just documented**: any stack-specific variable
whose value legitimately differs from another stack's same-named variable
must get a distinct name in `envs/*.tfvars` — hit and fixed twice during this
migration (`instance_type` → `toolkit_instance_type`, `ami_id` →
`toolkit_ami_id`). See [`terraform/README.md`](terraform/README.md).

## CI/CD — what runs on every push and PR

| Workflow | Trigger | What it does |
|---|---|---|
| `deploy-dev.yml` | push to `dev` (path-filtered: `terraform/**`, `workflows/wusool-toolkit/**`) | Builds + pushes toolkit image to `wusool-dev/toolkit`, applies `base → n8n → toolkit → postgres`, rolls the toolkit app via SSM, verifies `/health` returns 200 |
| `deploy-prod.yml` | push to `main`, same path filter | Identical, against `wusool-prod/toolkit` and `envs/prod.tfvars` |
| `_build.yml` | called by the two above | Builds the Dockerfile, pushes to that environment's own ECR repo, reuses the existing image if the commit was already built (repos are immutable-tag) |
| `_deploy.yml` | called by the two above | The actual per-stack `init`/`apply` sequence + bootstrap poll + health check + records `deployed_sha` to SSM on success only |
| `terraform-plan.yml` | any PR touching `terraform/**` | Comments a plan per stack per environment (5 jobs: `base`/`n8n`/`toolkit`/`postgres` × the PR's **base branch** environment, plus `account`). Read-only OIDC role (`wusool-gha-plan`) |
| `terraform-ci.yml` | any PR touching `terraform/**` | `tofu fmt -check` + `tofu validate` per stack |
| `ci.yml` | PR touching the app/scripts | `ruff check`, `ty check` (matching-engine), `pytest` run separately for the toolkit root, `matching-engine`, and `ddl-commands` (each has its own `testpaths`, so one invocation from the root silently missed the other two — fixed in code review 2026-08-16), PSScriptAnalyzer (`Severity=Error` only) |
| `backmerge.yml` | after a successful `Deploy prod` run | Opens an automatic `main → dev` PR if `dev` doesn't already have everything from `main` |

**No static AWS credentials anywhere.** All auth is GitHub OIDC
(`token.actions.githubusercontent.com`) assuming one of three branch-scoped
IAM roles:

- `wusool-gha-plan` — read-only, any branch/PR
- `wusool-gha-apply-dev` — trust-policy scoped to `refs/heads/dev`
- `wusool-gha-apply-prod` — trust-policy scoped to `refs/heads/main`

## Deploy verification — what "done" means now

A `tofu apply` returning success only proves the SSM bootstrap document was
*registered* — not that the app deployed. Three separate broken toolkit
deploys reported "Apply complete!" while the bootstrap had actually failed,
earlier in this restructure. `_deploy.yml` never trusts the exit code alone:

1. Apply registers a bootstrap document pointing at the new pinned digest.
2. `aws ssm send-command` re-invokes it (apply alone does not run it).
3. Poll `get-command-invocation` until `Success`/`Failed`/`Cancelled`/`TimedOut` — never just fire-and-forget.
4. `curl .../health` in a retry loop until `200`.
5. Only then, write `/wusool/<env>/toolkit/deployed_sha` to SSM.

## ECR / digest-pull deploy (Phase F)

- `toolkit-ec2`'s `user_data.sh.tpl` no longer clones a repo or builds on the
  instance. It does `aws ecr get-login-password | docker login`, then
  `docker compose pull` + `up -d` against `image: <registry>/<repo>@sha256:<digest>`.
- Each environment has its **own** ECR repository (`wusool-dev/toolkit`,
  `wusool-prod/toolkit`) — dev and prod never share a registry or a build.
- IAM: `ecr:GetAuthorizationToken` (account-level action, `Resource: "*"`)
  plus `BatchCheckLayerAvailability`/`GetDownloadUrlForLayer`/`BatchGetImage`
  scoped to that environment's own repo ARN.
- Verified live on dev, not just planned: real image built and pushed
  (`sha256:ad9e212f...`), applied, SSM bootstrap polled to `Success`, `/health`
  returned 200, and the **exact running container's** image digest confirmed
  to match the pinned value (`docker image inspect --format '{{json .RepoDigests}}'`
  on the instance).
- Prod's toolkit instance does not exist yet (`create_instance = false` in
  `envs/prod.tfvars`) — a deliberate, separate decision. `image_digest` for
  prod is currently an inert placeholder; it must be set to a real digest
  before that flag is ever flipped to `true`.

## AMI pinning (H1)

Both `n8n-ec2` and `toolkit-ec2` replaced `data "aws_ami" { most_recent = true }`
+ `lifecycle { ignore_changes = [ami] }` with an explicit `ami_id` variable
(`ami_id` for n8n, `toolkit_ami_id` for toolkit — kept distinct to avoid the
shared-tfvars collision above), pinned to whatever AMI each instance is
currently, verifiably running. `ignore_changes = [ami]` is kept as
belt-and-braces. Verified zero-diff across all four n8n/toolkit × dev/prod
combinations after the change.

## Prod database

RDS PostgreSQL provisioned for prod, seeded from a dev snapshot (cheapest way
to get a schema-identical starting point). Snapshot restore silently inherits
the source's master credentials via `manage_master_user_password` — caught
and fixed with a follow-up apply that rotates prod onto its own distinct
managed secret, never sharing dev's.

Prod's database is provisioned but is **not yet the system of record** for
n8n's live data — migrating n8n's data plane onto Postgres (H2) is explicitly
deferred, see below.

## Repo hygiene

- `.github/CODEOWNERS` — `@sinanshamsudheen` + `@raoofnaushad` required for
  everything, with infra (`/terraform/`, `/.github/workflows/`) explicitly
  called out.
- `main` branch retired: tagged `archive/main-pre-restructure` (pushed) before
  deletion. `dev` is now the sole active branch target.
- Two orphaned, empty `me-central-1` VPCs (`n8n-dev-vpc`, `n8n-prod-vpc`) —
  re-verified empty (zero instances/NAT/EIPs/ENIs) immediately before
  deletion, not just trusted from an earlier finding — fully deleted
  (subnets, route tables, IGWs, then the VPCs).
- `terraform/README.md` added — explains the modules/stacks/envs split, the
  five-stack table, apply-order dependency, and the shared-tfvars collision
  risk as a named, permanent rule.
- Root `README.md` rewritten to match this architecture (was still
  describing the pre-restructure `terraform/environments/` layout, an
  unbuilt `ddl-commands` placeholder, and no CD at all).

## What this branch does NOT do (explicitly deferred)

Per explicit scope decision, not started in this branch:

- **Phase G — Alembic + SQLAlchemy models** as the DDL source of truth for
  all tables in `wusool_crm`. The flat `database/sql/00*.sql` files remain
  authoritative for now.
- **H2 — migrate n8n's data plane onto Postgres**, making the n8n EC2
  instance's local state disposable.
- **H3 — a recurring AWS Backup / DLM snapshot policy.** Only the one-time,
  manual snapshots taken during this restructure exist today.
- **Scribe integration.** Scribe (meeting transcription) still runs its own,
  separate Terraform/state/deploy path, entirely outside this stacks/CD
  model — see [`SCRIBE_INFRA_CONTRACT.md`](SCRIBE_INFRA_CONTRACT.md) for the
  handover contract it would need to follow to plug in.
- **No human approval gate on prod.** A merge to `main` applies to
  production with no confirmation click between merge and AWS changing. This
  is an accepted risk, not an oversight — `backmerge.yml` is the chosen,
  no-extra-click mitigation for the specific failure mode of a hotfix being
  silently lost on the next promotion. See `RESTRUCTURE_PROGRESS.md` for the
  full accepted-risks reasoning.
- **No per-stack change detection.** Every stack is applied on every deploy,
  unconditionally (each apply is a no-op if nothing changed) — path-filtered
  "only deploy what changed" was the plan's original design but is a
  follow-up, documented directly in `_deploy.yml`'s header comment, not an
  accidental gap.

## Code review fixes (2026-08-16)

A `/code-review high` pass over this branch's diff against `dev` found and
fixed seven issues before merge:

1. **IAM self-escalation** — `stacks/account`'s `gha_apply_iam` policy
   granted `iam:CreateRole`/`AttachRolePolicy`/etc. on `Resource: "*"`,
   meaning the dev deploy role could grant itself admin, or edit the prod
   role's permissions, despite the branch-scoped trust policy. Scoped to
   `wusool-<env>-*` roles/instance-profiles only, `PassRole` further
   restricted to `iam:PassedToService = ec2.amazonaws.com`, plus an explicit
   `Deny` on touching the `gha-*` roles or the OIDC provider as defense in
   depth.
2. **`ignore_changes = [ami]` survived the H1 AMI-pinning fix** in both
   `n8n-ec2` and `toolkit-ec2` — meaning bumping `ami_id` in `envs/*.tfvars`
   still produced zero plan diff, exactly the problem H1 was supposed to
   fix. Removed from both modules.
3. **Most of the app's test suite silently never ran in CI** — `ci.yml` ran
   `pytest` once from the toolkit root, which only picks up that
   directory's own `testpaths`; `matching-engine`'s and `ddl-commands`' 117
   combined tests never executed. Now run separately per package.
4. **`gha_plan`'s state policy had `s3:DeleteObject`/`PutObject`** it never
   needed — `terraform-plan.yml` always runs with `-lock=false` and never
   writes. Scoped to `GetObject`/`ListBucket`.
5. **Duplicated init/setup boilerplate** across `terraform-ci.yml`,
   `terraform-plan.yml`, and `_deploy.yml` — extracted into composite
   actions (`.github/actions/setup-opentofu`, `aws-oidc`, `tofu-apply-stack`,
   `tofu-plan-comment`) so a future fix lands once, not three or four times.
6. **No Docker layer cache** in `_build.yml` — every merge rebuilt every
   layer from scratch. Added a GHA-backed buildx cache shared across dev and
   prod builds.
7. **Four overlapping root docs**, one with a misspelled filename —
   `restrcuture_progress.md` renamed to `RESTRUCTURE_PROGRESS.md`;
   `PROGRESS.md`'s infra section (stale since 2026-08-11, predating this
   whole restructure) replaced with a pointer to this file and
   `RESTRUCTURE_PROGRESS.md` instead of a fourth competing narrative.
