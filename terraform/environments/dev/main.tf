# Reads stacks/base — network, CloudTrail, the alerts SNS topic — which was
# migrated out of this root via `state mv` (Phase D). This root now owns only
# the compute/data services; the shared layer lives in stacks/base/envs/dev.tfvars.
data "terraform_remote_state" "base" {
  backend = "s3"
  config = {
    bucket = "wusool-tfstate"
    key    = "wusool/dev/base/terraform.tfstate"
    region = "me-central-1"
  }
}

data "terraform_remote_state" "n8n" {
  backend = "s3"
  config = {
    bucket = "wusool-tfstate"
    key    = "wusool/dev/n8n/terraform.tfstate"
    region = "me-central-1"
  }
}

data "terraform_remote_state" "toolkit" {
  backend = "s3"
  config = {
    bucket = "wusool-tfstate"
    key    = "wusool/dev/toolkit/terraform.tfstate"
    region = "me-central-1"
  }
}


module "postgres" {
  source = "../../modules/postgres-rds"

  project     = var.project
  environment = var.environment
  vpc_id      = data.terraform_remote_state.base.outputs.vpc_id
  subnet_ids  = data.terraform_remote_state.base.outputs.database_private_subnet_ids
  allowed_security_group_ids = [
    data.terraform_remote_state.n8n.outputs.security_group_id,
    data.terraform_remote_state.toolkit.outputs.security_group_id,
    "sg-0684b8cf83abfd065",
  ]
  db_name           = var.postgres_db_name
  master_username   = var.postgres_master_username
  engine_version    = var.postgres_engine_version
  instance_class    = var.postgres_instance_class
  allocated_storage = var.postgres_allocated_storage
}


# ---------------------------------------------------------------------------
# Container registry - ONE REPOSITORY PER ENVIRONMENT.
#
# Each environment builds and stores its own images: dev images never appear in
# prod's registry and vice versa, so there is no cross-environment coupling and
# no shared blast radius on the registry.
#
# Trade-off accepted: prod builds its own artifact rather than promoting the one
# dev validated, so the two are not guaranteed byte-identical. `uv.lock` pins
# every Python dependency, but the Dockerfile's base images are pinned by TAG
# (python:3.12-slim-bookworm), which moves. To make the builds genuinely
# reproducible, pin those by digest in the Dockerfile.
# ---------------------------------------------------------------------------

