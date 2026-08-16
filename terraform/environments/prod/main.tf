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

module "n8n" {
  source = "../../modules/n8n-ec2"

  project                     = var.project
  environment                 = var.environment
  vpc_id                      = data.terraform_remote_state.base.outputs.vpc_id
  subnet_id                   = data.terraform_remote_state.base.outputs.public_subnet_id
  key_name                    = var.key_name
  instance_type               = var.instance_type
  ami_architecture            = var.ami_architecture
  ssh_cidr_blocks             = var.ssh_cidr_blocks
  web_cidr_blocks             = var.web_cidr_blocks
  expose_n8n_port             = var.expose_n8n_port
  n8n_webhook_url             = var.n8n_webhook_url
  n8n_timezone                = var.n8n_timezone
  root_volume_size            = var.root_volume_size
  alarm_topic_arn             = data.terraform_remote_state.base.outputs.alarm_topic_arn
  secrets_manager_secret_arns = [aws_secretsmanager_secret.n8n.arn]
  n8n_secret_id               = aws_secretsmanager_secret.n8n.id
  additional_hostnames        = var.n8n_additional_hostnames
  n8n_image                   = var.n8n_image
  runners_image               = var.runners_image
  caddy_image                 = var.caddy_image
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
resource "aws_secretsmanager_secret" "n8n" {
  name                    = "/${var.project}/${var.environment}/n8n"
  description             = "Environment-specific n8n secrets for ${var.project} ${var.environment}"
  recovery_window_in_days = 30
}

module "postgres" {
  source = "../../modules/postgres-rds"

  project     = var.project
  environment = var.environment
  vpc_id      = data.terraform_remote_state.base.outputs.vpc_id
  subnet_ids  = data.terraform_remote_state.base.outputs.database_private_subnet_ids

  allowed_security_group_ids = [
    module.n8n.security_group_id,
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

resource "aws_ecr_repository" "wusool_toolkit" {
  name = "${var.project}-${var.environment}/toolkit"

  # IMMUTABLE means a tag can never be repointed at different content after an
  # environment has validated it. Required for digest promotion to mean anything.
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

resource "aws_ecr_lifecycle_policy" "wusool_toolkit" {
  repository = aws_ecr_repository.wusool_toolkit.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep the last 30 images; untagged layers expire quickly."
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 30
        }
        action = { type = "expire" }
      }
    ]
  })
}
