# Update feed for the WusoolScribe desktop app's Tauri auto-updater: an S3
# bucket behind CloudFront serving a per-channel latest.json manifest plus the
# signed .app.tar.gz/.sig payloads it points at. Not per-environment - the
# axis of variation is the release channel (stable/beta), which lives in the
# S3 key prefix, not in a dev/prod split. See docs/dev/SCRIBE_UPDATE_FEED.md.
#
# The artifacts are downloaded unauthenticated by every installed app, by
# design - that is not a leak. Integrity comes from Tauri's minisign
# signature (verified client-side against the pubkey baked into the app),
# not from access control. This bucket stays private/OAC-only anyway, so
# there is exactly one cache/log surface rather than a second public S3 URL
# people bookmark alongside the CloudFront one.

data "aws_caller_identity" "current" {}

data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

# ---------------------------------------------------------------------------
# S3 - private, CloudFront is the only reader
# ---------------------------------------------------------------------------

resource "aws_s3_bucket" "updates" {
  bucket        = "${var.project}-scribe-updates-${data.aws_caller_identity.current.account_id}"
  force_destroy = false
}

resource "aws_s3_bucket_public_access_block" "updates" {
  bucket                  = aws_s3_bucket.updates.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "updates" {
  bucket = aws_s3_bucket.updates.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# A bad latest.json push (wrong version, wrong signature) is recoverable by
# restoring the previous object version, without rebuilding anything.
resource "aws_s3_bucket_versioning" "updates" {
  bucket = aws_s3_bucket.updates.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "updates" {
  bucket = aws_s3_bucket.updates.id
  rule {
    id     = "expire-noncurrent-versions"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }
}

# ---------------------------------------------------------------------------
# CloudFront - Origin Access Control (OAC), default *.cloudfront.net domain.
# No custom domain in pass one: it would need an ACM cert in us-east-1 (a
# second provider alias) plus DNS this repo does not manage, and the
# updater only needs a stable HTTPS URL - the default domain is stable for
# the distribution's lifetime.
# ---------------------------------------------------------------------------

resource "aws_cloudfront_origin_access_control" "updates" {
  name                              = "${var.project}-scribe-updates"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

data "aws_cloudfront_cache_policy" "optimized" {
  name = "Managed-CachingOptimized"
}

data "aws_cloudfront_cache_policy" "disabled" {
  name = "Managed-CachingDisabled"
}

resource "aws_cloudfront_distribution" "updates" {
  enabled      = true
  comment      = "WusoolScribe desktop update feed"
  price_class  = var.cloudfront_price_class
  http_version = "http2and3"

  origin {
    domain_name              = aws_s3_bucket.updates.bucket_regional_domain_name
    origin_id                = "s3-updates"
    origin_access_control_id = aws_cloudfront_origin_access_control.updates.id
  }

  # Immutable versioned artifacts (scribe/<channel>/<version>/...): long TTL.
  default_cache_behavior {
    target_origin_id       = "s3-updates"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    viewer_protocol_policy = "redirect-to-https"
    compress               = true
    cache_policy_id        = data.aws_cloudfront_cache_policy.optimized.id
  }

  # The mutable manifest: no caching, so a release is visible immediately
  # and never needs a client to wait out a stale edge cache.
  ordered_cache_behavior {
    path_pattern           = "scribe/*/latest.json"
    target_origin_id       = "s3-updates"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    viewer_protocol_policy = "redirect-to-https"
    compress               = true
    cache_policy_id        = data.aws_cloudfront_cache_policy.disabled.id
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

data "aws_iam_policy_document" "bucket" {
  statement {
    sid       = "AllowCloudFrontRead"
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.updates.arn}/*"]

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.updates.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "updates" {
  bucket = aws_s3_bucket.updates.id
  policy = data.aws_iam_policy_document.bucket.json
}

# ---------------------------------------------------------------------------
# Release role - narrowly scoped to this bucket + distribution only, not the
# PowerUser gha_apply roles (stacks/account). Publishing a desktop binary
# must not carry the ability to reshape the account.
#
# Branch-scoping the trust (like gha_apply's ref:refs/heads/<env>) doesn't
# work here: this is a public repo and the release is triggered by
# workflow_dispatch from arbitrary branches, so a ref:refs/heads/* condition
# would let anyone with push access ship an update to every installed app.
# Gate on a GitHub Environment instead - the "environment:" claim only
# appears when the job declares it, so this narrows the role to jobs that
# declare `environment: scribe-release`. The environment itself needs no
# protection rules (no required reviewers) - workflow_dispatch already
# requires write access to trigger, which is the actual gate; the
# environment here is purely an OIDC-trust label, and job_workflow_ref
# additionally pins the one workflow file allowed to assume this role. See
# docs/dev/SCRIBE_UPDATE_FEED.md for the one-time step of creating the
# environment.
# ---------------------------------------------------------------------------

locals {
  scribe_release_environment = "scribe-release"
}

data "aws_iam_policy_document" "release_trust" {
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
      values   = ["repo:${var.github_repo}:environment:${local.scribe_release_environment}"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:job_workflow_ref"
      values   = ["${var.github_repo}/.github/workflows/scribe-release.yml@*"]
    }
  }
}

resource "aws_iam_role" "gha_scribe_release" {
  name               = "${var.project}-gha-scribe-release"
  description        = "GitHub Actions: publish WusoolScribe desktop update artifacts."
  assume_role_policy = data.aws_iam_policy_document.release_trust.json
}

# No s3:DeleteObject, no s3:* - a release workflow never deletes. Overwrites
# of an existing version's tarball remain possible; bucket versioning plus
# the minisign signature make that recoverable and non-exploitable. Multipart
# actions are required - the .app.tar.gz is well over the 8MB threshold.
resource "aws_iam_role_policy" "gha_scribe_release_publish" {
  name = "${var.project}-gha-scribe-release-publish"
  role = aws_iam_role.gha_scribe_release.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "PublishArtifacts"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:AbortMultipartUpload",
          "s3:ListMultipartUploadParts",
        ]
        Resource = "${aws_s3_bucket.updates.arn}/scribe/*"
      },
      {
        Sid      = "ListBucket"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = aws_s3_bucket.updates.arn
      },
      {
        Sid      = "InvalidateManifest"
        Effect   = "Allow"
        Action   = ["cloudfront:CreateInvalidation"]
        Resource = aws_cloudfront_distribution.updates.arn
      }
    ]
  })
}
