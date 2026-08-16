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

module "matching_engine" {
  source = "../../modules/matching-engine-ec2"

  project                     = var.project
  environment                 = var.environment
  vpc_id                      = module.network.vpc_id
  subnet_id                   = module.network.public_subnet_id
  key_name                    = var.key_name
  instance_type               = var.matching_engine_instance_type
  ami_architecture            = var.ami_architecture
  ssh_cidr_blocks             = var.ssh_cidr_blocks
  web_cidr_blocks             = var.web_cidr_blocks
  git_repo_url                = var.matching_engine_git_repo_url
  git_ref                     = var.matching_engine_git_ref
  root_volume_size            = var.root_volume_size
  aws_region                  = var.aws_region
  alarm_topic_arn             = aws_sns_topic.alerts.arn
  secrets_manager_secret_arns = [aws_secretsmanager_secret.matching_engine.arn]

  # Single entry, single process: matching-engine and ddl-commands are one
  # Slack bot (one token, one interactivity URL — see
  # workflows/wusool-toolkit/README.md), built from the toolkit root's
  # Dockerfile, not matching-engine's own subdirectory. This module's `apps`
  # list still supports multiple entries for a future, genuinely separate
  # bot on this same instance — this just isn't one.
  apps = [
    {
      name          = "matching-engine"
      app_subdir    = "workflows/wusool-toolkit"
      app_secret_id = aws_secretsmanager_secret.matching_engine.id
      public_url    = var.matching_engine_public_url
    }
  ]
}

module "matching_engine_bedrock" {
  source = "../../modules/bedrock-access"

  project       = var.project
  environment   = "${var.environment}-matching-engine"
  iam_role_name = module.matching_engine.iam_role_name
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
    module.matching_engine.security_group_id,
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
resource "aws_secretsmanager_secret" "matching_engine" {
  name                    = "/${var.project}/${var.environment}/matching-engine"
  description             = "Environment-specific matching-engine secrets for ${var.project} ${var.environment}"
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

resource "aws_guardduty_detector" "this" {
  enable = true
}

resource "aws_securityhub_account" "this" {}

# ---------------------------------------------------------------------------
# Security finding routing (Defect 5)
#
# GuardDuty and Security Hub are ACCOUNT-level singletons — one detector covers
# both VPCs — so their findings belong to neither dev nor prod. They get their
# own topic rather than borrowing a per-environment infrastructure topic, which
# also keeps "a box is unhealthy" separate from "someone may be attacking us".
#
# These resources live here only because the detector above does. They move to
# stacks/account via `state mv` when Phase D lands — no re-creation.
# ---------------------------------------------------------------------------

resource "aws_sns_topic" "security_alerts" {
  name = "${var.project}-security-alerts"
}

resource "aws_sns_topic_subscription" "security_email" {
  count     = var.alert_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.security_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

data "aws_iam_policy_document" "security_alerts" {
  statement {
    sid       = "AllowEventBridgePublish"
    effect    = "Allow"
    actions   = ["SNS:Publish"]
    resources = [aws_sns_topic.security_alerts.arn]

    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_sns_topic_policy" "security_alerts" {
  arn    = aws_sns_topic.security_alerts.arn
  policy = data.aws_iam_policy_document.security_alerts.json
}

# GuardDuty: MEDIUM and above (severity >= 4). LOW is mostly policy noise such
# as the RootCredentialUsage findings already sitting unreviewed.
resource "aws_cloudwatch_event_rule" "guardduty_findings" {
  name        = "${var.project}-guardduty-findings"
  description = "GuardDuty findings of MEDIUM severity or higher"

  event_pattern = jsonencode({
    source        = ["aws.guardduty"]
    "detail-type" = ["GuardDuty Finding"]
    detail = {
      severity = [{ numeric = [">=", 4] }]
    }
  })
}

resource "aws_cloudwatch_event_target" "guardduty_to_sns" {
  rule      = aws_cloudwatch_event_rule.guardduty_findings.name
  target_id = "security-alerts"
  arn       = aws_sns_topic.security_alerts.arn

  input_transformer {
    input_paths = {
      severity    = "$.detail.severity"
      type        = "$.detail.type"
      description = "$.detail.description"
      region      = "$.region"
      account     = "$.account"
      time        = "$.time"
    }
    input_template = <<-TEMPLATE
      "GuardDuty finding (severity <severity>) in <account>/<region> at <time>"
      "Type: <type>"
      ""
      "<description>"
    TEMPLATE
  }
}

# Security Hub: only HIGH/CRITICAL, still ACTIVE and not yet triaged. Without
# these filters the 14 LOW CIS metric-filter findings would arrive as spam and
# the routing would be switched off within a week.
resource "aws_cloudwatch_event_rule" "securityhub_findings" {
  name        = "${var.project}-securityhub-findings"
  description = "New HIGH/CRITICAL Security Hub findings"

  event_pattern = jsonencode({
    source        = ["aws.securityhub"]
    "detail-type" = ["Security Hub Findings - Imported"]
    detail = {
      findings = {
        Severity    = { Label = ["HIGH", "CRITICAL"] }
        Workflow    = { Status = ["NEW"] }
        RecordState = ["ACTIVE"]
      }
    }
  })
}

resource "aws_cloudwatch_event_target" "securityhub_to_sns" {
  rule      = aws_cloudwatch_event_rule.securityhub_findings.name
  target_id = "security-alerts"
  arn       = aws_sns_topic.security_alerts.arn
}
