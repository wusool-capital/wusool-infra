module "network" {
  source = "../../modules/network"

  project                      = var.project
  environment                  = var.environment
  vpc_cidr                     = var.vpc_cidr
  public_subnet_cidr           = var.public_subnet_cidr
  private_subnet_cidr          = var.private_subnet_cidr
  database_private_subnet_cidr = var.database_private_subnet_cidr
}

module "n8n" {
  source = "../../modules/n8n-ec2"

  project                     = var.project
  environment                 = var.environment
  vpc_id                      = module.network.vpc_id
  subnet_id                   = module.network.public_subnet_id
  key_name                    = var.key_name
  instance_type               = var.instance_type
  ami_architecture            = var.ami_architecture
  ssh_cidr_blocks             = var.ssh_cidr_blocks
  web_cidr_blocks             = var.web_cidr_blocks
  expose_n8n_port             = var.expose_n8n_port
  n8n_webhook_url             = var.n8n_webhook_url
  n8n_timezone                = var.n8n_timezone
  root_volume_size            = var.root_volume_size
  alarm_topic_arn             = aws_sns_topic.alerts.arn
  secrets_manager_secret_arns = [aws_secretsmanager_secret.n8n.arn]
  n8n_secret_id               = aws_secretsmanager_secret.n8n.id
  additional_hostnames        = var.n8n_additional_hostnames
  n8n_image                   = var.n8n_image
  runners_image               = var.runners_image
  caddy_image                 = var.caddy_image
}

module "bedrock" {
  source = "../../modules/bedrock-access"

  project       = var.project
  environment   = var.environment
  iam_role_name = module.n8n.iam_role_name
  models        = var.bedrock_models
}

module "wusool_toolkit" {
  source = "../../modules/toolkit-ec2"

  project                     = var.project
  environment                 = var.environment
  vpc_id                      = module.network.vpc_id
  subnet_id                   = module.network.public_subnet_id
  key_name                    = var.key_name
  instance_type               = var.wusool_toolkit_instance_type
  ami_architecture            = var.ami_architecture
  ssh_cidr_blocks             = var.ssh_cidr_blocks
  web_cidr_blocks             = var.web_cidr_blocks
  git_repo_url                = var.wusool_toolkit_git_repo_url
  git_ref                     = var.wusool_toolkit_git_ref
  root_volume_size            = var.root_volume_size
  aws_region                  = var.aws_region
  alarm_topic_arn             = aws_sns_topic.alerts.arn
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
  vpc_id      = module.network.vpc_id
  subnet_ids  = module.network.database_private_subnet_ids
  allowed_security_group_ids = [
    module.n8n.security_group_id,
    module.wusool_toolkit.security_group_id,
    "sg-0684b8cf83abfd065",
  ]
  db_name           = var.postgres_db_name
  master_username   = var.postgres_master_username
  engine_version    = var.postgres_engine_version
  instance_class    = var.postgres_instance_class
  allocated_storage = var.postgres_allocated_storage
}

data "aws_caller_identity" "current" {}

resource "aws_sns_topic" "alerts" {
  name = "${var.project}-${var.environment}-infrastructure-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  count     = var.alert_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_secretsmanager_secret" "n8n" {
  name                    = "/${var.project}/${var.environment}/n8n"
  description             = "Environment-specific n8n secrets for ${var.project} ${var.environment}"
  recovery_window_in_days = 30
}

# Populate the secret value out of band (console, or `aws secretsmanager
# put-secret-value`) with JSON: {"slack_bot_token": "...",
# "slack_signing_secret": "...", "database_url": "postgresql://...",
# "github_token": "..."}. Never put real secrets in a .tf file or state diff.
resource "aws_secretsmanager_secret" "wusool_toolkit" {
  name                    = "/${var.project}/${var.environment}/toolkit"
  description             = "Environment-specific wusool-toolkit secrets for ${var.project} ${var.environment}"
  recovery_window_in_days = 30
}

resource "aws_s3_bucket" "cloudtrail" {
  bucket        = "${var.project}-${var.environment}-cloudtrail-${data.aws_caller_identity.current.account_id}"
  force_destroy = false
}

resource "aws_s3_bucket_public_access_block" "cloudtrail" {
  bucket                  = aws_s3_bucket.cloudtrail.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_policy" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Sid = "CloudTrailAclCheck", Effect = "Allow", Principal = { Service = "cloudtrail.amazonaws.com" }, Action = "s3:GetBucketAcl", Resource = aws_s3_bucket.cloudtrail.arn },
      { Sid = "CloudTrailWrite", Effect = "Allow", Principal = { Service = "cloudtrail.amazonaws.com" }, Action = "s3:PutObject", Resource = "${aws_s3_bucket.cloudtrail.arn}/AWSLogs/${data.aws_caller_identity.current.account_id}/*", Condition = { StringEquals = { "s3:x-amz-acl" = "bucket-owner-full-control" } } }
    ]
  })
}

resource "aws_cloudtrail" "this" {
  name                          = "${var.project}-${var.environment}"
  s3_bucket_name                = aws_s3_bucket.cloudtrail.id
  include_global_service_events = true
  is_multi_region_trail         = true
  enable_log_file_validation    = true
  depends_on                    = [aws_s3_bucket_policy.cloudtrail]
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
