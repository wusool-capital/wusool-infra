# wusool-scribe — infrastructure contract

> **Source of truth:** this document is generated from Part 2 of
> `Final_restructure_plan.md` in the `wusool-infra` repo. If the two disagree,
> that plan wins. Regenerate rather than editing both.
>
> Every fact below was verified against AWS account `030179310793` on
> 2026-08-15, not taken from documentation.

**Audience:** whoever owns the `wusool-scribe` repo. It tells you how to stand up
**scribe dev and scribe prod** so they plug into the restructured `wusool-infra`
conventions.

---

## What changed and why you're reading this

`wusool-infra` has been restructured so that every service is defined **once**
and deployed to `dev` or `prod` by swapping a backend key and a var-file. Scribe
is currently deployed to dev only, from its own state, outside that convention.
Following this contract lets you stand up **scribe dev and scribe prod** the
same way every other service works.

## Where scribe stands today (verified live)

| Fact | Value |
|---|---|
| Instance | `wusool-scribe` / `i-01bf509a92ed1dcba`, **c6a.xlarge** |
| VPC | `vpc-0ed8db2cc2b5f2cdc` — **the dev VPC** |
| Security group | `sg-0684b8cf83abfd065` (`wusool-scribe-instance`) |
| State | `s3://wusool-tfstate/wusool/dev/scribe/terraform.tfstate`, serial 15, written by 1.10.6 |
| Structure | Flat root module — all resources at root, no `module` blocks |
| Secret | `/wusool-scribe` |
| Owns | EC2, SGs, S3 buckets, SQS queue, Secrets Manager secret, SSM document |
| Tags | **No `Environment` tag** |
| Database | Writes `meetings` in `wusool_crm` via the least-privilege `scribe_pub` role; has its own Alembic chain |

Good news: **your backend key already matches the new convention**
(`wusool/<env>/<service>/terraform.tfstate`). Scribe is the existing precedent
that per-service state works here.

## The contract — what scribe must do to plug in

**1. Toolchain.** Match the version pinned in
`wusool-infra/terraform/.opentofu-version`. Your state is at 1.10.6 while
wusool-infra's is at 1.15.6. **Do not let anyone apply scribe's state with the
newer binary before you have decided to upgrade** — it upgrades the state in
place and your current tooling may stop reading it.

**2. Backend keys.** Keep the existing dev key; add prod:

```
wusool/dev/scribe/terraform.tfstate      # exists
wusool/prod/scribe/terraform.tfstate     # new
```

Bucket `wusool-tfstate`, **region `me-central-1`** (state region deliberately
differs from the resource region — do not "fix" it). Use `use_lockfile = true`;
there is no DynamoDB lock table.

**3. One stack, two environments.** Replace any env-specific directories with a
single root using a partial backend:

```hcl
terraform { backend "s3" {} }
```

```bash
tofu init -reconfigure \
  -backend-config="bucket=wusool-tfstate" \
  -backend-config="region=me-central-1" \
  -backend-config="key=wusool/$ENV/scribe/terraform.tfstate" \
  -backend-config="use_lockfile=true" -backend-config="encrypt=true"
tofu apply -var-file=envs/$ENV.tfvars
```

Commit `envs/dev.tfvars` and `envs/prod.tfvars`. Non-secret values (region,
CIDRs, instance type, domains) **belong in git** — they are configuration, not
secrets. Their absence from version control is precisely how wusool-infra's prod
drift went unnoticed.

**4. Stop creating your own network. Consume the base layer.**

Scribe currently runs inside the dev VPC with its own SGs. Under the new model,
networking is owned by `stacks/base` per environment. Read it:

```hcl
data "terraform_remote_state" "base" {
  backend = "s3"
  config = {
    bucket = "wusool-tfstate"
    key    = "wusool/${var.environment}/base/terraform.tfstate"
    region = "me-central-1"
  }
}
```

Available outputs: `vpc_id`, `public_subnet_id`, `private_subnet_id`,
`database_private_subnet_ids`, `alarm_topic_arn`.

Use `alarm_topic_arn` for your CloudWatch alarms rather than creating a second
SNS topic. **Do not create a GuardDuty detector or enable SecurityHub** — they
are account-level singletons already owned by `stacks/account`, and a second one
will fail the apply.

**5. Attach yourself to Postgres — don't ask to be added to a list.**

`wusool-infra` currently hardcodes `"sg-0684b8cf83abfd065"` (your dev SG) in the
RDS ingress allow-list. Under the new model that inverts: **`stacks/postgres`
exports its SG ID and owns no allow-list; each consumer creates its own ingress
rule.** In scribe's stack:

```hcl
data "terraform_remote_state" "postgres" {
  backend = "s3"
  config = {
    bucket = "wusool-tfstate"
    key    = "wusool/${var.environment}/postgres/terraform.tfstate"
    region = "me-central-1"
  }
}

resource "aws_vpc_security_group_ingress_rule" "postgres" {
  security_group_id            = data.terraform_remote_state.postgres.outputs.security_group_id
  referenced_security_group_id = aws_security_group.scribe.id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
  tags = { Name = "scribe-${var.environment}", Consumer = "scribe" }
}
```

**This is the answer to "do I have to add the SG per environment?" — no.** The
same code, applied with `dev.tfvars` or `prod.tfvars`, reads that environment's
Postgres SG and attaches that environment's scribe SG. Nobody edits
`wusool-infra`, and nobody pastes an SG ID.

Also export your own SG so other services can reference it:

```hcl
output "security_group_id" { value = aws_security_group.scribe.id }
```

Apply order per environment: `base` → `postgres` → `scribe`.

**6. Naming and tagging.** Every resource: `wusool-<env>-scribe-<thing>`.
Set `default_tags` in the provider — `Project`, `Environment`, `ManagedBy =
"terraform"`, `Owner`. Scribe's instance currently has **no `Environment` tag**,
which is why it doesn't show up in environment-filtered queries and cost reports.

**7. Rename the secret.** `/wusool-scribe` → `/wusool/<env>/scribe`, matching
`/wusool/dev/n8n`, `/wusool/prod/n8n`, `/wusool/dev/matching-engine`. Scribe prod
needs its own secret; **do not share the dev secret across environments.**

**8. Never bake a script into an SSM document and re-run the stale copy.**

This is the most expensive lesson in this account. `aws_ssm_document.bootstrap`
holds an *embedded copy* of the rendered `user_data` frozen at the last apply.
Re-running it regenerates config from that stale copy and silently reverts live
fixes. **It has broken wusool-infra's production three times**, and as of this
survey the registered prod n8n document still pointed at a hostname retired in
August — invoking it would have taken production down.

Scribe has the identical structure. The invariants:
- The bootstrap document **must be re-registered from current source as part of
  every deploy**.
- A deploy path of "re-run the existing document" must never be the *only*
  option.
- If you ship an app-redeploy workflow that only calls `ssm send-command`,
  **document explicitly** that it cannot pick up a template change without an
  apply first.

**9. Build once, deploy by digest.** Do not `git clone` + `docker build` on the
instance. Build in CI, push to ECR, deploy by `sha256:` digest, so dev and prod
run the identical artifact. Instances are in the public subnet with EIPs, so no
NAT or VPC endpoint is required. Pin every base image.

**10. Branching and CD.** `dev` + `prod`. Merge to `dev` deploys dev; merge to
`prod` deploys prod. Plan-on-PR is a required status check on **both** branches,
and the plan must select its var-file from the PR's **base** branch — otherwise
your promotion PR shows a dev diff while prod is what changes. Use GitHub OIDC
(role ARNs from `stacks/account`); no static AWS keys.

**11. Database — DDL ownership is settled; scribe is a data client only.**

**wusool-infra owns 100% of `wusool_crm` DDL.** Scribe has read/write on the
`meetings` *data* via the least-privilege `scribe_pub` role and **applies no
migrations**. Keep it that way:

- Scribe must **not** run Alembic, `CREATE TABLE`, or `ALTER TABLE` against
  `wusool_crm`. Two migration chains on one database corrupt each other's
  version table.
- Scribe's DB user keeps `scribe_pub` only. Do not grant DDL.
- **If scribe needs a schema change to `meetings`, request it in wusool-infra**
  — it lands as an Alembic revision there. Treat the schema as an API owned by
  another team.
- wusool-infra carries the `scribe_pub` role and its GRANTs (currently
  `database/sql/005_meetings.sql`) into a hand-written Alembic revision, since
  autogenerate cannot see roles or grants.
- Scribe should keep a **read-only** drift check (reflect the live schema,
  assert the columns it depends on still exist) so a wusool-infra migration that
  breaks scribe fails loudly in scribe's CI rather than at runtime.

**Sequencing: prod has no database yet.** `wusool-infra`'s `stacks/postgres` for
prod is created in wusool-infra's Phase F. **Scribe prod cannot be deployed until that
exists.**

## Checklist to add scribe dev + prod

- [ ] Toolchain is **OpenTofu**, version matching `wusool-infra/terraform/.opentofu-version`
- [ ] Single root with partial backend; `envs/dev.tfvars` + `envs/prod.tfvars` committed
- [ ] Consumes `stacks/base` remote state for VPC/subnets/SNS
- [ ] Creates no GuardDuty detector and does not enable SecurityHub
- [ ] Exports `security_group_id`
- [ ] `wusool-<env>-scribe-*` naming; `default_tags` incl. `Environment`
- [ ] Secret renamed to `/wusool/<env>/scribe`; separate secret per env
- [ ] SSM document re-registered from source on every deploy
- [ ] Image built in CI, pushed to ECR, deployed by digest; base images pinned
- [ ] OIDC auth; plan-on-PR required on `dev` and `prod`, var-file from base ref
- [ ] DDL ownership agreed (a/b/c above) and written down
- [ ] `stacks/postgres` prod exists before scribe prod is applied

---
