# ---------------------------------------------------------------------------
# Account-level resources — applied ONCE, not per environment.
#
# GuardDuty is one-detector-per-account-per-region and Security Hub is
# per-account, so these CANNOT live in a per-environment stack: applying such a
# stack for a second environment fails on both resources.
#
# Security findings are account-wide, so they route to their own topic rather
# than borrowing a per-environment infrastructure topic.
#
# Migrated from terraform/environments/dev by `state mv` — never destroyed and
# recreated. Re-creating aws_securityhub_account discards finding history and
# per-control configuration accumulated since 2026-06-21.
# ---------------------------------------------------------------------------

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
