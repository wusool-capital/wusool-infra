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
