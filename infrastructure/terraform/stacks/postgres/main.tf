# PostgreSQL — one stack, per environment via envs/*.tfvars. Reads stacks/base
# for network, and stacks/n8n + stacks/toolkit for consumer security groups.
# Migrated via `state mv` (Phase D).
#
# toolkit's security_group_id is null when that stack has create_instance =
# false (prod, until a toolkit instance is deliberately created) — compact()
# drops the null so the ingress list never contains an empty entry.

locals {
  allowed_security_group_ids = concat(
    [data.terraform_remote_state.n8n.outputs.security_group_id],
    compact([data.terraform_remote_state.toolkit.outputs.security_group_id]),
    var.extra_allowed_security_group_ids,
  )
}

# extra_allowed_security_group_ids on prod is scribe's dev-VPC SG — reachable
# only via the wusool-dev-to-prod peering connection (stacks/peering, applied
# out of band). Without this check, applying prod's SG grant before peering
# exists doesn't fail loudly: AWS accepts a security-group rule referencing an
# SG in another VPC as long as SOME peering connection links the two VPCs, so
# a stale/wrong peering setup could silently leave the rule non-functional.
# Plural data source (not aws_vpc_peering_connection) deliberately: it returns
# an empty list instead of erroring when nothing matches yet.
#
# The blocking assertion lives in this data source's own `postcondition`, NOT
# a top-level `check` block — `check` block assertion failures are warnings
# only (confirmed live against OpenTofu 1.12.5: apply still exits 0), which
# would let deploy-prod.yml's unattended `tofu apply -auto-approve` sail
# straight through a missing/broken peering connection. A postcondition on a
# resource/data block genuinely fails plan and apply.
data "aws_vpc_peering_connections" "dev_to_prod" {
  count = var.environment == "prod" && length(var.extra_allowed_security_group_ids) > 0 ? 1 : 0

  filter {
    name   = "tag:Name"
    values = ["wusool-dev-to-prod"]
  }

  filter {
    name   = "status-code"
    values = ["active"]
  }

  lifecycle {
    postcondition {
      condition     = length(self.ids) > 0
      error_message = "extra_allowed_security_group_ids on prod grants cross-VPC ingress, but no active 'wusool-dev-to-prod' VPC peering connection exists yet. Apply stacks/peering first."
    }
  }
}

module "postgres" {
  source = "../../modules/postgres-rds"

  project     = var.project
  environment = var.environment
  vpc_id      = data.terraform_remote_state.base.outputs.vpc_id
  subnet_ids  = data.terraform_remote_state.base.outputs.database_private_subnet_ids

  allowed_security_group_ids = local.allowed_security_group_ids

  db_name             = var.db_name
  master_username     = var.master_username
  engine_version      = var.engine_version
  instance_class      = var.instance_class
  allocated_storage   = var.allocated_storage
  snapshot_identifier = var.snapshot_identifier
}
