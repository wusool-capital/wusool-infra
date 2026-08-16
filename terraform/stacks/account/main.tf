# Account-level resources — applied ONCE, no per-environment split.
#
# Migrated from terraform/environments/dev via `state mv` (Phase D). GuardDuty
# and Security Hub are account+region singletons; the GitHub OIDC provider and
# its roles are trusted by the whole repo, not one environment.

data "aws_caller_identity" "current" {}

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

# ---------------------------------------------------------------------------
# Terraform/OpenTofu state bucket — the backend every stack (including this
# one) reads from. Adopted from terraform/bootstrap/ via `tofu import`
# (Phase D, §D0a) rather than recreated: the bucket already existed and holds
# every stack's live state.
#
# prevent_destroy is not optional here: a `tofu destroy` on this stack must
# never be able to delete the bucket holding its own state and every other
# stack's state.
#
# The DynamoDB lock table that used to live in terraform/bootstrap/ is
# deliberately NOT here. Both backends use `use_lockfile = true`
# (S3-native locking), so the table was unused — verified zero references in
# every stack's state before deletion — and was removed from AWS directly on
# 2026-08-15. Recreating it here would just resurrect dead weight.
# ---------------------------------------------------------------------------

resource "aws_s3_bucket" "tfstate" {
  provider = aws.tfstate_bucket

  bucket = "wusool-tfstate"

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "tfstate" {
  provider = aws.tfstate_bucket

  bucket = aws_s3_bucket.tfstate.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
  provider = aws.tfstate_bucket

  bucket = aws_s3_bucket.tfstate.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "tfstate" {
  provider = aws.tfstate_bucket

  bucket = aws_s3_bucket.tfstate.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
