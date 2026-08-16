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

# ---------------------------------------------------------------------------
# Container registry (Phase F)
#
# ONE repository shared by dev and prod. That is the whole point of
# build-once/deploy-by-digest: prod runs the byte-identical image dev tested,
# so a per-environment repository would defeat it.
#
# Account-scoped like GuardDuty above, and lives here only because that is where
# the account-level resources currently sit. Moves to stacks/account by
# `state mv` in Phase D.
# ---------------------------------------------------------------------------

resource "aws_ecr_repository" "wusool_toolkit" {
  name = "${var.project}/toolkit"

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

# ---------------------------------------------------------------------------
# GitHub Actions OIDC (Phase E)
#
# Account-level: one provider, one set of roles, trusted by this repo only.
# Short-lived tokens - no static AWS keys ever stored in GitHub.
# Moves to stacks/account by `state mv` in Phase D.
# ---------------------------------------------------------------------------

resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

locals {
  github_repo = "wusool-capital/wusool-infra"
}

# Read-only + state access. Used by plan-on-PR from ANY branch, so it must never
# be able to mutate infrastructure.
data "aws_iam_policy_document" "gha_plan_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${local.github_repo}:*"]
    }
  }
}

resource "aws_iam_role" "gha_plan" {
  name               = "${var.project}-gha-plan"
  description        = "GitHub Actions: terraform plan and read-only inspection."
  assume_role_policy = data.aws_iam_policy_document.gha_plan_trust.json
}

resource "aws_iam_role_policy_attachment" "gha_plan_readonly" {
  role       = aws_iam_role.gha_plan.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

# Plan needs to write the state lock and read state, which ReadOnlyAccess alone
# does not permit.
resource "aws_iam_role_policy" "gha_plan_state" {
  name = "${var.project}-gha-plan-state"
  role = aws_iam_role.gha_plan.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
        Resource = ["arn:aws:s3:::wusool-tfstate", "arn:aws:s3:::wusool-tfstate/*"]
      }
    ]
  })
}

# Apply roles, scoped by BRANCH via the OIDC `sub` claim. A workflow running on
# `dev` cannot assume the prod role and vice versa - the branch restriction is
# enforced by AWS at AssumeRole time, not by workflow logic that could be edited.
data "aws_iam_policy_document" "gha_apply_trust" {
  for_each = toset(["dev", "prod"])

  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # Exact branch match, plus the matching GitHub Environment. workflow_dispatch
    # on the same branch is covered by the first value.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "repo:${local.github_repo}:ref:refs/heads/${each.key}",
        "repo:${local.github_repo}:environment:${each.key}",
      ]
    }
  }
}

resource "aws_iam_role" "gha_apply" {
  for_each = toset(["dev", "prod"])

  name               = "${var.project}-gha-apply-${each.key}"
  description        = "GitHub Actions: terraform apply for the ${each.key} environment."
  assume_role_policy = data.aws_iam_policy_document.gha_apply_trust[each.key].json
}

# PowerUserAccess + targeted IAM. Deliberately not AdministratorAccess: the
# deploy needs to manage service resources and their roles, not reshape the
# account's own security posture.
resource "aws_iam_role_policy_attachment" "gha_apply_power" {
  for_each = aws_iam_role.gha_apply

  role       = each.value.name
  policy_arn = "arn:aws:iam::aws:policy/PowerUserAccess"
}

resource "aws_iam_role_policy" "gha_apply_iam" {
  for_each = aws_iam_role.gha_apply

  name = "${var.project}-gha-apply-iam"
  role = each.value.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "iam:CreateRole", "iam:DeleteRole", "iam:GetRole", "iam:ListRoles",
          "iam:TagRole", "iam:UntagRole", "iam:UpdateRole",
          "iam:PutRolePolicy", "iam:DeleteRolePolicy", "iam:GetRolePolicy", "iam:ListRolePolicies",
          "iam:AttachRolePolicy", "iam:DetachRolePolicy", "iam:ListAttachedRolePolicies",
          "iam:CreateInstanceProfile", "iam:DeleteInstanceProfile", "iam:GetInstanceProfile",
          "iam:AddRoleToInstanceProfile", "iam:RemoveRoleFromInstanceProfile",
          "iam:PassRole", "iam:CreateServiceLinkedRole"
        ]
        Resource = "*"
      }
    ]
  })
}

output "gha_role_arns" {
  description = "Role ARNs for GitHub Actions OIDC. Not secret - safe to reference directly in workflow YAML."
  value = {
    plan       = aws_iam_role.gha_plan.arn
    apply_dev  = aws_iam_role.gha_apply["dev"].arn
    apply_prod = aws_iam_role.gha_apply["prod"].arn
  }
}
