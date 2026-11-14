# Public downloads. Today that is the two template files that /bulk-buyer and
# /bulk-seller link to when an uploaded file is not the template. Not
# per-environment: the files are the same for dev and prod. The Slack app's
# "wrong template" message links straight to these objects.
#
# This bucket is public on purpose, and only for the `templates/` prefix. The
# files hold column headers and no business data. Never put anything else under
# that prefix, and nothing sensitive anywhere in this bucket: a public read
# policy can't tell one file from another.
#
# Expect Security Hub to flag this bucket (AWS Foundational Security Best
# Practices, the S3 "block public access" controls) once it is applied. The
# account stack alerts on new HIGH findings, so the first apply may page. The
# public read is intended: suppress those findings with a note saying so.
#
# The template files are owned by the server code (the field definitions build
# them), so this stack uploads the committed copies and a unit test fails when
# they drift. After changing a field, regenerate and commit them, then apply
# this stack out of band, like stacks/scribe-updates.

data "aws_caller_identity" "current" {}

locals {
  templates_dir = "${path.module}/../../../../server/app/modules/ddl_commands/bulk_templates"
  templates     = toset(["buyer-template.csv", "seller-template.csv"])
}

resource "aws_s3_bucket" "assets" {
  bucket        = "${var.project}-assets-${data.aws_caller_identity.current.account_id}"
  force_destroy = false
}

# Public read comes only from the bucket policy below, scoped to one prefix.
# ACLs stay blocked, so no object can be made public one by one.
resource "aws_s3_bucket_public_access_block" "assets" {
  bucket                  = aws_s3_bucket.assets.id
  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_server_side_encryption_configuration" "assets" {
  bucket = aws_s3_bucket.assets.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# A bad template push is recoverable by restoring the previous object version.
resource "aws_s3_bucket_versioning" "assets" {
  bucket = aws_s3_bucket.assets.id
  versioning_configuration {
    status = "Enabled"
  }
}

data "aws_iam_policy_document" "public_templates" {
  statement {
    sid       = "PublicReadTemplates"
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.assets.arn}/templates/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
  }
}

resource "aws_s3_bucket_policy" "assets" {
  bucket = aws_s3_bucket.assets.id
  policy = data.aws_iam_policy_document.public_templates.json

  # The policy is refused while the public access block still blocks policies.
  depends_on = [aws_s3_bucket_public_access_block.assets]
}

resource "aws_s3_object" "templates" {
  for_each = local.templates

  bucket = aws_s3_bucket.assets.id
  key    = "templates/${each.key}"
  source = "${local.templates_dir}/${each.key}"
  etag   = filemd5("${local.templates_dir}/${each.key}")

  content_type = "text/csv; charset=utf-8"
  # Makes a click download the file instead of showing it in the browser.
  content_disposition = "attachment; filename=\"${each.key}\""
  cache_control       = "no-cache"
}
