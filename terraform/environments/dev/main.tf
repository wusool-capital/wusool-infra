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

module "wusool_toolkit" {
  source = "../../modules/toolkit-ec2"

  project                     = var.project
  environment                 = var.environment
  vpc_id                      = data.terraform_remote_state.base.outputs.vpc_id
  subnet_id                   = data.terraform_remote_state.base.outputs.public_subnet_id
  key_name                    = var.key_name
  instance_type               = var.wusool_toolkit_instance_type
  ami_architecture            = var.ami_architecture
  ssh_cidr_blocks             = var.ssh_cidr_blocks
  web_cidr_blocks             = var.web_cidr_blocks
  git_repo_url                = var.wusool_toolkit_git_repo_url
  git_ref                     = var.wusool_toolkit_git_ref
  root_volume_size            = var.root_volume_size
  aws_region                  = var.aws_region
  alarm_topic_arn             = data.terraform_remote_state.base.outputs.alarm_topic_arn
  secrets_manager_secret_arns = [aws_secretsmanager_secret.wusool_toolkit.arn]

  # Single entry, single process: matching-engine and ddl-commands are one
  # Slack bot (one token, one interactivity URL — see
  # workflows/wusool-toolkit/README.md), built from the toolkit root's
  # Dockerfile, not matching-engine's own subdirectory. This module's `apps`
  # list still supports multiple entries for a future, genuinely separate
  # bot on this same instance — this just isn't one.
  apps = [
    {
      name          = "toolkit"
      app_subdir    = "workflows/wusool-toolkit"
      app_secret_id = aws_secretsmanager_secret.wusool_toolkit.id
      public_url    = var.wusool_toolkit_public_url
    }
  ]
}

module "wusool_toolkit_bedrock" {
  source = "../../modules/bedrock-access"

  project       = var.project
  environment   = "${var.environment}-toolkit"
  iam_role_name = module.wusool_toolkit.iam_role_name
  models        = var.bedrock_models
}

module "postgres" {
  source = "../../modules/postgres-rds"

  project     = var.project
  environment = var.environment
  vpc_id      = data.terraform_remote_state.base.outputs.vpc_id
  subnet_ids  = data.terraform_remote_state.base.outputs.database_private_subnet_ids
  allowed_security_group_ids = [
    data.terraform_remote_state.n8n.outputs.security_group_id,
    module.wusool_toolkit.security_group_id,
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

# Populate the secret value out of band (console, or `aws secretsmanager
# put-secret-value`) with JSON: {"slack_bot_token": "...",
# "slack_signing_secret": "...", "database_url": "postgresql://...",
# "github_token": "..."}. Never put real secrets in a .tf file or state diff.
resource "aws_secretsmanager_secret" "wusool_toolkit" {
  name                    = "/${var.project}/${var.environment}/toolkit"
  description             = "Environment-specific wusool-toolkit secrets for ${var.project} ${var.environment}"
  recovery_window_in_days = 30
}

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
