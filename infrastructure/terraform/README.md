# terraform/

```
terraform/
  .opentofu-version   # pinned OpenTofu version — install this exact version locally
  modules/            # HOW each resource is built (reusable, environment-agnostic)
  stacks/             # WHAT to build per service — the roots you actually apply
  envs/                # WHICH values — one committed tfvars file per environment
```

This repo is managed with **OpenTofu**, not HashiCorp Terraform — see the root
[`CONTRIBUTING.md`](../CONTRIBUTING.md) for why that distinction matters and
how to install it. Do not run `terraform` against this repo.

## Modules vs. stacks — why both exist

- **`modules/`** defines *how* a resource is built: the `aws_instance`, its
  security group, its `user_data.sh.tpl` bootstrap script. A module never
  declares a backend and is never applied directly.
- **`stacks/`** defines *what* to build for a given service: which modules to
  call, which cross-stack values to read, which backend key to write state to.
  Stacks are the roots you actually `init`/`plan`/`apply`.

Multiple stacks share the same module — e.g. `stacks/n8n` and `stacks/toolkit`
both call `modules/bedrock-access`. Fix a bug in a module once, and every stack
that uses it picks up the fix on its next apply. This is also why you cannot
delete `modules/` and inline everything into `stacks/`: every stack's
`source = "../../modules/..."` line depends on it, and dev/prod would drift
out of sync with each other without it.

## The stacks

| Stack | Owns | Per-environment? |
|---|---|---|
| `account` | GuardDuty, Security Hub, security-alert routing, GitHub OIDC provider + roles, the `wusool-tfstate` state bucket itself | **No** — applied once, no `-var-file` |
| `base` | VPC, subnets, CloudTrail, the infrastructure-alerts SNS topic | Yes |
| `n8n` | The n8n EC2 instance, its secret, optional Bedrock access | Yes |
| `toolkit` | The wusool-toolkit EC2 instance (an Auto Scaling Group of size 1, not a standalone `aws_instance` — self-heals on termination/hardware failure and keeps its Elastic IP across replacement), its secret, its own ECR repo | Yes |
| `postgres` | The RDS instance, seeded from a snapshot if `snapshot_identifier` is set | Yes |
| `peering` | The dev↔prod VPC peering connection and its routes | **No** — spans both environments |
| `scribe-updates` | S3 + CloudFront update feed for the WusoolScribe desktop app, and the GitHub OIDC role that publishes to it | **No** — one public feed, not per-environment (see [`docs/dev/SCRIBE_UPDATE_FEED.md`](../../docs/dev/SCRIBE_UPDATE_FEED.md)) |

Every per-environment stack reads `stacks/base`'s network/alarm outputs via
`terraform_remote_state`; `postgres` also reads `n8n` and `toolkit`'s security
group IDs the same way. Apply order for a **new** environment:
`base` → `n8n` and `toolkit` → `postgres` (postgres needs the others' security
groups to already exist in state).

**`stacks/toolkit` has a `create_instance` variable.** It gates the EC2
instance separately from the ECR repo and secret, so those can exist ahead of
any billable compute. Corrected 2026-09-09: this section previously said prod
defaulted to `false`; `envs/prod.tfvars` has set `create_instance = true`
since 2026-08-17 and the prod toolkit instance is live.

**One container can serve several hostnames.** Each `apps` entry takes
`extra_hostnames`, joined into Caddy's comma-separated site addresses, so a
second audience gets its own hostname without its own process — this is how
`tools.wusoolcapital.com` reaches the lead-magnet tools, which are routers
and static files inside the same toolkit image. Prefer this over a second
`apps` entry unless you genuinely need process isolation: a second entry
needs its own Secrets Manager secret and IAM ARN, its own ECR repo and pull
policy, a second image build in `_build.yml`, and `_deploy.yml`'s migration,
health-check and `deployed_sha` steps all name `toolkit` literally. It also
would not isolate failure the way it looks like it does — `apps` renders one
docker-compose file and one SSM bootstrap, so an app that cannot start fails
every app's rollout.

> **DNS must exist before you apply a new hostname.** Caddy orders a
> certificate per site address at config load. A name that does not yet
> resolve to the instance's Elastic IP fails HTTP-01, burns Let's Encrypt's
> five-failures-per-hostname-per-hour budget, and then stays broken on
> Caddy's own backoff well past the point DNS is fixed. DNS is manual in
> Cloudflare, not in this repo — and keep the record grey-cloud (DNS only),
> or Cloudflare's edge caches `embed.js` past its 60s TTL and every rollback
> needs a manual purge.

## Applying a stack

Each stack uses a **partial backend** — no bucket/key hardcoded in the repo —
so the same directory serves every environment:

```bash
cd terraform/stacks/n8n
tofu init -reconfigure \
  -backend-config=bucket=wusool-tfstate \
  -backend-config=region=me-central-1 \
  -backend-config=key=wusool/<env>/n8n/terraform.tfstate \
  -backend-config=use_lockfile=true \
  -backend-config=encrypt=true

tofu plan  -var-file=../../envs/<env>.tfvars
tofu apply -var-file=../../envs/<env>.tfvars
```

Replace `<env>` with `dev` or `prod`, and `n8n` with any stack name (`base`,
`toolkit`, `postgres`). `stacks/account` takes no `-var-file` — it isn't
per-environment.

In CI, `.github/workflows/_deploy.yml` does exactly this for every per-env
stack, in order, on every push to `dev`/`prod`. `terraform-plan.yml` does the
read-only version on every PR and comments the diff.

## `envs/*.tfvars`

One committed file per environment, shared across every stack that needs it.
Because it's one flat file read by several stacks' `-var-file`, **two rules
matter**:

1. A variable declared by more than one stack with the **same name but a
   different intended value** will silently take whichever value the shared
   file has — OpenTofu does not error on unrecognized `-var-file` keys, only a
   suppressible warning. (This bit us once already: `instance_type` collided
   between `stacks/n8n` and `stacks/toolkit` until the toolkit one was renamed
   `toolkit_instance_type`.) Before adding a variable to a stack, check
   whether another stack already uses that name for something else.
2. A **duplicate key** across two sections of the same `.tfvars` file is a
   hard parse error, not a warning — if two stacks genuinely want the same
   value (e.g. `key_name`), declare it once and let both stacks read it; don't
   repeat the assignment.

Secrets never go in these files. They live in AWS Secrets Manager, referenced
by ARN and fetched at runtime by the instance's own IAM role.

## First time here

1. Install the pinned OpenTofu version (`.opentofu-version`) — see
   [`CONTRIBUTING.md`](../CONTRIBUTING.md).
2. Never run a stack without first checking whether `terraform_remote_state`
   dependencies (`base`, and for `postgres`, also `n8n`/`toolkit`) already
   exist for that environment. A `plan` will fail loudly with "Unsupported
   attribute" if a dependency's outputs haven't been populated yet — that
   just means run `apply` on the dependency first.
3. Before applying anything to `prod`, read a stack's `plan` output for
   `forces replacement` or `will be destroyed` — there is no approval gate
   between merge and apply (see the plan doc's *Accepted risks*), so the PR
   plan comment is the only human review production gets.
