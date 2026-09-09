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

# Slack relay for the same alerts topic every alarm in this environment
# already notifies — one new subscriber, no per-alarm changes anywhere else.
# Both envs point at the same Slack workspace/channel; the environment is
# already visible in each alarm's own name (e.g. wusool-prod-toolkit-...).
#
# Gated on both IDs being set, same pattern as alert_email above: the
# one-time Slack workspace authorization happens by hand in the AWS Chatbot
# console (no Terraform resource for that step exists), so this stays a
# no-op until that's done and the resulting IDs are in tfvars.
resource "aws_iam_role" "chatbot_alerts" {
  count = var.slack_team_id != "" && var.slack_channel_id != "" ? 1 : 0

  name = "${var.project}-${var.environment}-chatbot-alerts"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "chatbot.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

# AWS's own documented minimum for notification-only use (relaying
# CloudWatch/SNS alarms into a chat room, no interactive AWS commands run
# from Slack): https://docs.aws.amazon.com/chatbot/latest/adminguide/chatbot-iam-policies.html#read-only-notifications-policy
# — deliberately not ReadOnlyAccess or CloudWatchReadOnlyAccess, both far
# broader than an alert relay needs.
resource "aws_iam_role_policy" "chatbot_notifications_only" {
  count = length(aws_iam_role.chatbot_alerts)

  name = "${var.project}-${var.environment}-chatbot-notifications-only"
  role = aws_iam_role.chatbot_alerts[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["cloudwatch:Describe*", "cloudwatch:Get*", "cloudwatch:List*"]
      Resource = "*"
    }]
  })
}

resource "aws_chatbot_slack_channel_configuration" "alerts" {
  count = var.slack_team_id != "" && var.slack_channel_id != "" ? 1 : 0

  configuration_name = "${var.project}-${var.environment}-alerts"
  iam_role_arn       = aws_iam_role.chatbot_alerts[0].arn
  slack_channel_id   = var.slack_channel_id
  slack_team_id      = var.slack_team_id
  sns_topic_arns     = [aws_sns_topic.alerts.arn]
  logging_level      = "ERROR"
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

