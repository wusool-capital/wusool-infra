# CI deploy credentials. The Cloudflare token lives in Secrets Manager and is
# read at deploy time through GitHub OIDC - no long-lived secret in GitHub.

data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

# Only the container is managed here. The token is put with
# `aws secretsmanager put-secret-value`, so it never reaches OpenTofu state.
resource "aws_secretsmanager_secret" "cloudflare_deploy" {
  name        = "/${var.project}/engine-frontend/cloudflare-deploy"
  description = "Cloudflare API token used by deploy-engine.yml to run wrangler deploy."
}

# The repo is public, so trust is pinned to one workflow file on one branch.
# A feature branch with write access cannot dispatch it and read the token.
data "aws_iam_policy_document" "deploy_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repo}:environment:engine-dev"]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:job_workflow_ref"
      values   = ["${var.github_repo}/.github/workflows/deploy-engine.yml@refs/heads/dev"]
    }
  }

  # The live Engine deploys from `prod` into its own GitHub environment. A separate statement, so a
  # dev run can never present the prod environment, or the other way round.
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repo}:environment:engine-prod"]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:job_workflow_ref"
      values   = ["${var.github_repo}/.github/workflows/deploy-engine.yml@refs/heads/prod"]
    }
  }
}

resource "aws_iam_role" "gha_engine_deploy" {
  name               = "${var.project}-gha-engine-deploy"
  description        = "GitHub Actions: read the Cloudflare deploy token for the Engine."
  assume_role_policy = data.aws_iam_policy_document.deploy_trust.json
}

resource "aws_iam_role_policy" "gha_engine_deploy_read_secret" {
  name = "${var.project}-gha-engine-deploy-read-secret"
  role = aws_iam_role.gha_engine_deploy.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "ReadCloudflareDeployToken"
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = aws_secretsmanager_secret.cloudflare_deploy.arn
    }]
  })
}
