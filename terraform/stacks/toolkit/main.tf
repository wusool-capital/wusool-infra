# wusool-toolkit service — one stack, per environment via envs/*.tfvars.
# Reads stacks/base for network + alarm topic. Migrated via `state mv` (Phase D).

# Populate the secret value out of band with JSON: {"slack_bot_token": "...",
# "slack_signing_secret": "...", "database_url": "postgresql://...",
# "github_token": "...", "env": {"ATTIO_API_KEY": "...",
# "ATTIO_WEBHOOK_SECRET": "..."}}. ddl-commands' Settings requires both
# ATTIO_API_KEY and ATTIO_WEBHOOK_SECRET unconditionally (see
# ddl-commands/ddl_commands/config.py) — omitting either fails Settings()
# construction on the very first request that touches the database, for
# every command, not just the Attio-writing ones (user_data.sh.tpl's
# `env: {}` passthrough is the generic mechanism for this, already handles
# any extra key without further templating). ATTIO_WEBHOOK_SECRET is the
# value Attio returns exactly once, in the response to `POST /v2/webhooks` —
# see the webhook-registration runbook handed over separately. Never put
# real secrets in a .tf file or state diff.
resource "aws_secretsmanager_secret" "wusool_toolkit" {
  name                    = "/${var.project}/${var.environment}/toolkit"
  description             = "Environment-specific wusool-toolkit secrets for ${var.project} ${var.environment}"
  recovery_window_in_days = 30
}

module "wusool_toolkit" {
  count  = var.create_instance ? 1 : 0
  source = "../../modules/toolkit-ec2"

  project                     = var.project
  environment                 = var.environment
  vpc_id                      = data.terraform_remote_state.base.outputs.vpc_id
  subnet_id                   = data.terraform_remote_state.base.outputs.public_subnet_id
  key_name                    = var.key_name
  instance_type               = var.toolkit_instance_type
  ssh_cidr_blocks             = var.ssh_cidr_blocks
  ami_id                      = var.toolkit_ami_id
  web_cidr_blocks             = var.web_cidr_blocks
  root_volume_size            = var.toolkit_root_volume_size
  aws_region                  = var.aws_region
  alarm_topic_arn             = data.terraform_remote_state.base.outputs.alarm_topic_arn
  secrets_manager_secret_arns = [aws_secretsmanager_secret.wusool_toolkit.arn]
  ecr_repository_arn          = aws_ecr_repository.wusool_toolkit.arn

  # Single entry, single process: matching-engine and ddl-commands are one
  # Slack bot (one token, one interactivity URL — see
  # workflows/wusool-toolkit/README.md), built from the toolkit root's
  # Dockerfile. This module's `apps` list still supports multiple entries for
  # a future, genuinely separate bot on this same instance — this just isn't one.
  apps = [
    {
      name          = "toolkit"
      image         = "${aws_ecr_repository.wusool_toolkit.repository_url}@${var.image_digest}"
      app_secret_id = aws_secretsmanager_secret.wusool_toolkit.id
      public_url    = var.public_url
    }
  ]
}

module "bedrock" {
  count  = var.enable_bedrock && var.create_instance ? 1 : 0
  source = "../../modules/bedrock-access"

  project       = var.project
  environment   = "${var.environment}-toolkit"
  iam_role_name = module.wusool_toolkit[0].iam_role_name
  models        = var.bedrock_models
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
