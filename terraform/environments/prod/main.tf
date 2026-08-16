# Reads stacks/base — network, CloudTrail, the alerts SNS topic — which was
# migrated out of this root via `state mv` (Phase D). This root now owns only
# the compute/data services; the shared layer lives in stacks/base/envs/prod.tfvars.
data "terraform_remote_state" "base" {
  backend = "s3"
  config = {
    bucket = "wusool-tfstate"
    key    = "wusool/prod/base/terraform.tfstate"
    region = "me-central-1"
  }
}

data "terraform_remote_state" "n8n" {
  backend = "s3"
  config = {
    bucket = "wusool-tfstate"
    key    = "wusool/prod/n8n/terraform.tfstate"
    region = "me-central-1"
  }
}

data "terraform_remote_state" "toolkit" {
  backend = "s3"
  config = {
    bucket = "wusool-tfstate"
    key    = "wusool/prod/toolkit/terraform.tfstate"
    region = "me-central-1"
  }
}



# ---------------------------------------------------------------------------
# Production PostgreSQL
#
# A dedicated prod instance — prod must never share a database with dev. Sized
# to the cheapest viable option (db.t4g.micro, 20 GiB gp3, single-AZ), matching
# dev, with storage autoscaling to 100 GiB.
#
# Access is granted per consuming service's security group. n8n is included so
# the documented SSM port-forwarding runbook works against prod the same way it
# does in dev; n8n itself stores nothing here (it uses SQLite on its own volume).
# wusool-toolkit prod joins this list when its stack is created.
#
# The master password is RDS-managed and rotated; read it from the secret ARN in
# the postgres_master_user_secret_arn output, never from configuration.
# ---------------------------------------------------------------------------
module "postgres" {
  source = "../../modules/postgres-rds"

  project     = var.project
  environment = var.environment
  vpc_id      = data.terraform_remote_state.base.outputs.vpc_id
  subnet_ids  = data.terraform_remote_state.base.outputs.database_private_subnet_ids

  allowed_security_group_ids = [
    data.terraform_remote_state.n8n.outputs.security_group_id,
  ]

  db_name           = var.postgres_db_name
  master_username   = var.postgres_master_username
  engine_version    = var.postgres_engine_version
  instance_class    = var.postgres_instance_class
  allocated_storage = var.postgres_allocated_storage

  # Seeded from a dev snapshot so prod starts with the same schema AND data.
  # Note this carries dev's rows - including any test/experimental records -
  # into a production database. db_name and master_username above are ignored
  # while this is set; both come from the snapshot.
  snapshot_identifier = var.postgres_snapshot_identifier
}
