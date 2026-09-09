# Per-environment shared layer: network, CloudTrail, and the infrastructure
# alerts topic. Applied once per environment (dev.tfvars / prod.tfvars) via a
# partial backend — one copy of this code, two independent states.
#
# Migrated from terraform/environments/{dev,prod}/main.tf via `state mv`
# (Phase D).

data "aws_caller_identity" "current" {}

module "network" {
  source = "../../modules/network"

  project                      = var.project
  environment                  = var.environment
  vpc_cidr                     = var.vpc_cidr
  public_subnet_cidr           = var.public_subnet_cidr
  private_subnet_cidr          = var.private_subnet_cidr
  database_private_subnet_cidr = var.database_private_subnet_cidr
}

resource "aws_sns_topic" "alerts" {
  name = "${var.project}-${var.environment}-infrastructure-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  count     = var.alert_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# us-east-1 twin of the alerts topic, for alarms that must live there —
# today that's just the toolkit's Route 53 reachability alarm (PutMetricAlarm
# rejects a cross-region action ARN for AWS/Route53 alarms specifically).
#
# The Slack relay itself (IAM role + the one Chatbot channel configuration)
# is NOT here — it lives in stacks/account. AWS Chatbot allows only ONE
# configuration per Slack channel per AWS ACCOUNT, full stop — not one per
# region, and not one per environment either. Dev and prod share an
# account, so each environment trying to own its own config for the same
# #infra-alerts channel fails outright the moment the second one applies
# (InvalidRequestException: "already been configured for AWS account"),
# discovered via two separate live apply failures, 2026-09-09 — first
# cross-region within one environment, then cross-environment. The one
# shared config in stacks/account subscribes to both of this environment's
# topics (this one and the default-region `alerts` topic above) alongside
# the other environment's.
resource "aws_sns_topic" "alerts_us_east_1" {
  count    = var.slack_team_id != "" && var.slack_channel_id != "" ? 1 : 0
  provider = aws.us_east_1

  name = "${var.project}-${var.environment}-infrastructure-alerts-use1"
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

