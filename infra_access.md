# wusool-infra — grant scribe (dev VPC) access to wusool-prod-postgres

> **Audience:** whoever applies `wusool-infra`. Scribe-side code and CI are
> already done (see `wusool-scribe` PR #10) and inert until
> `WUSOOL_DATABASE_URL_PROD` is set — nothing here can be finished from the
> scribe repo. Every ID below was verified live against AWS account
> `030179310793` (profile `wusool`), not taken from tfvars alone.

## Why

Scribe now supports a second, client-facing Slack app whose meetings should
publish to `wusool-prod-postgres` / `wusool_crm` instead of dev's database
(`SlackTarget.PROD` — see `app/shared/enums` in `wusool-scribe`). The app
code and the `WUSOOL_DATABASE_URL_PROD` plumbing are already in place; the
only thing missing is that **scribe's EC2 instance cannot reach
wusool-prod-postgres at all**, at the network layer.

## The problem, precisely

Scribe's instance runs in the **dev** VPC. `wusool-prod-postgres` runs in the
**prod** VPC. There is no VPC peering, no Transit Gateway, and the RDS
instance is not publicly accessible — confirmed via `describe-vpc-peering-
connections` (empty) and `describe-transit-gateway-attachments` (empty).
An SG change alone does nothing here; there is currently no route between
the two VPCs at all.

| | Dev (scribe lives here) | Prod (the DB lives here) |
|---|---|---|
| VPC | `vpc-0ed8db2cc2b5f2cdc` | `vpc-00fd39371dfaae3bf` |
| CIDR | `10.10.0.0/16` | `10.20.0.0/16` |
| Scribe's subnet | `subnet-02ae652e6d178f86f` (public) | — |
| Scribe's subnet's route table | `rtb-0af5663be0f3bdf87` (`wusool-dev-public-rt`) | — |
| RDS's subnets | — | `subnet-0b8b5c89d6aeaaa67`, `subnet-045f5eb01c7624402` |
| RDS's subnets' route table | — | `rtb-0c262b9124bb89495` (`wusool-prod-private-rt`) |
| RDS security group | — | `sg-0a4875729e3424b9d` |
| Scribe's security group | `sg-0684b8cf83abfd065` (`wusool-scribe-instance`) | (same, referenced from prod side) |

## Why this can't be a quick `aws ec2 create-route` / console click

Both route tables above are Terraform-managed by `wusool-infra`'s
`modules/network`. `aws_route_table.public` (dev) already declares an
inline `route {}` block (the `0.0.0.0/0` default route) — inline route
blocks are **authoritative**: OpenTofu deletes any route it doesn't know
about on the next `tofu apply` of that stack. `aws_route_table.private`
(prod) declares zero inline routes today, which is the same trap in the
other direction — it's already "authoritatively empty," so a hand-added
route there survives only until the next apply removes it. **Anything
added out-of-band to either table will be silently deleted by a routine
`stacks/base` apply.** This has to go in as real Terraform.

## What to build

A **new peering connection** between the two VPCs, plus one route on each
side, added as standalone `aws_route` resources — not by editing
`modules/network`'s inline blocks, so this doesn't collide with normal
`stacks/base` applies or require touching every environment's shared
module.

### 1. Export what's needed from `stacks/base`

Neither `modules/network/outputs.tf` nor `stacks/base/outputs.tf` currently
exposes a route table ID or the VPC CIDR. Add, in `modules/network/outputs.tf`:

```hcl
output "public_route_table_id" {
  value = aws_route_table.public.id
}

output "private_route_table_id" {
  value = aws_route_table.private.id
}

output "vpc_cidr" {
  value = aws_vpc.this.cidr_block
}
```

And re-expose all three at `stacks/base/outputs.tf` (same pattern as the
existing `vpc_id`/`public_subnet_id` outputs there). Do this for **both**
`dev` and `prod` — same module, two environments, two applies.

### 2. New stack: `stacks/peering` (or fold into wherever you'd rather own
cross-environment resources — there isn't one today)

Reads both environments' `stacks/base` remote state, creates the peering
connection + acceptance, and the two routes:

```hcl
data "terraform_remote_state" "base_dev" {
  backend = "s3"
  config = {
    bucket = "wusool-tfstate"
    key    = "wusool/dev/base/terraform.tfstate"
    region = "me-central-1"
  }
}

data "terraform_remote_state" "base_prod" {
  backend = "s3"
  config = {
    bucket = "wusool-tfstate"
    key    = "wusool/prod/base/terraform.tfstate"
    region = "me-central-1"
  }
}

resource "aws_vpc_peering_connection" "dev_to_prod" {
  vpc_id      = data.terraform_remote_state.base_dev.outputs.vpc_id
  peer_vpc_id = data.terraform_remote_state.base_prod.outputs.vpc_id
  auto_accept = true # same account, same region — no cross-account handshake needed

  tags = { Name = "wusool-dev-to-prod" }
}

# dev's public route table (scribe's subnet) -> prod VPC, via the peering
resource "aws_route" "dev_to_prod" {
  route_table_id            = data.terraform_remote_state.base_dev.outputs.public_route_table_id
  destination_cidr_block    = data.terraform_remote_state.base_prod.outputs.vpc_cidr
  vpc_peering_connection_id = aws_vpc_peering_connection.dev_to_prod.id
}

# prod's private route table (the RDS's subnets) -> dev VPC, via the peering
resource "aws_route" "prod_to_dev" {
  route_table_id            = data.terraform_remote_state.base_prod.outputs.private_route_table_id
  destination_cidr_block    = data.terraform_remote_state.base_dev.outputs.vpc_cidr
  vpc_peering_connection_id = aws_vpc_peering_connection.dev_to_prod.id
}
```

Backend key: `wusool/shared/peering/terraform.tfstate` (or whatever this
account's convention is for a resource that isn't per-environment — it
spans both, so it doesn't belong under `wusool/dev/` or `wusool/prod/`).

**Scope check before applying:** `auto_accept = true` peers the *entire*
dev VPC to the *entire* prod VPC. Actual reachability stays gated by
security groups on the receiving side (same model scribe already uses
for its own dev DB access) — nothing in dev gets access to anything in
prod without also being separately allow-listed on that resource's SG.
Still, worth a conscious "yes" from whoever owns this, since it's a new
network path between environments that didn't exist before.

### 3. Security group — the actual access grant

Once the route exists, do the part that was already planned: add scribe's
SG to the RDS's ingress allow-list. In `stacks/postgres`'s **prod**
`main.tf`, `local.allowed_security_group_ids` already `concat()`s
`var.extra_allowed_security_group_ids` — mirror dev's exact pattern
(`terraform/envs/dev.tfvars` already has `extra_allowed_security_group_ids
= ["sg-0684b8cf83abfd065"]` for the equivalent dev grant). Add to
`terraform/envs/prod.tfvars` (currently has no such line at all):

```hcl
# stacks/postgres — prod
# sg-0684b8cf83abfd065 = wusool-scribe-instance. Cross-VPC (dev -> prod),
# reachable only via the wusool-dev-to-prod peering connection + its routes
# (stacks/peering) — see wusool-scribe's WUSOOL_INFRA_PROD_DB_ACCESS.md.
extra_allowed_security_group_ids = ["sg-0684b8cf83abfd065"]
```

Then apply `stacks/postgres` for prod.

### 4. Apply order

`stacks/base` (dev, for the new outputs) → `stacks/base` (prod, for the new
outputs) → `stacks/peering` (new) → `stacks/postgres` (prod, for the SG
grant). Verify with a `tofu plan` at each step that nothing outside what's
described here changes — in particular, `stacks/base`'s plan for both envs
should show **outputs only**, no resource changes.

### 5. The `scribe_pub` role itself

Not a Terraform concern, but don't forget it: `scribe_pub` currently exists
only on dev's `wusool_crm` (created manually per `database/sql/005_meetings.sql`'s
commented-out block). The identical role + grants need to exist on
**prod**'s `wusool_crm` before the DSN is worth anything:

```sql
CREATE ROLE scribe_pub LOGIN PASSWORD '<generate-a-strong-one>';
GRANT CONNECT ON DATABASE wusool_crm TO scribe_pub;
GRANT SELECT, INSERT, UPDATE ON meetings      TO scribe_pub;
GRANT SELECT                 ON organizations TO scribe_pub;
```

Run against `wusool-prod-postgres` (endpoint
`wusool-prod-postgres.cpuwqesq4v8p.eu-central-1.rds.amazonaws.com:5432`,
database `wusool_crm`) once the peering is live and reachable from wherever
you run this from.

## Handing the result back to scribe

Once all of the above is applied, the DSN to hand back is:

```
postgresql+asyncpg://scribe_pub:<password>@wusool-prod-postgres.cpuwqesq4v8p.eu-central-1.rds.amazonaws.com:5432/wusool_crm?ssl=require
```

That value becomes the `WUSOOL_DATABASE_URL_PROD` GitHub Actions secret on
`wusool-scribe` (`gh secret set WUSOOL_DATABASE_URL_PROD --repo
wusool-capital/wusool-scribe`) — the app and CI side are already wired to
pick it up with no further code change, and publishing for `SlackTarget.PROD`
meetings turns on the moment that secret is set and `terraform.yml` next
applies.

## Verification

- `tofu plan` on `stacks/base` (both envs) shows outputs added, nothing else.
- `tofu plan` on the new `stacks/peering` shows exactly 1 peering connection
  + 2 routes.
- `tofu plan` on `stacks/postgres` (prod) shows exactly 1 new ingress rule
  on `sg-0a4875729e3424b9d`.
- From scribe's instance (or any host in the dev VPC/subnet
  `subnet-02ae652e6d178f86f`):
  `psql "host=wusool-prod-postgres.cpuwqesq4v8p.eu-central-1.rds.amazonaws.com port=5432 dbname=wusool_crm user=scribe_pub sslmode=require"`
  connects.
- `curl https://<scribe-hostname>/health` still reports the existing
  (dev) `wusool_db: ok` unaffected, and once `WUSOOL_DATABASE_URL_PROD` is
  set, reports both targets `ok`.
