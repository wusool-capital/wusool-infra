# Public downloads: the /bulk-buyer and /bulk-seller template files. Not per-environment.

# Public on purpose, under `templates/` only. Keep anything sensitive out of this bucket.

# Expect Security Hub HIGH findings for the public bucket. Intended: suppress with a note.

# Templates are built from the field definitions. Apply out of band after changing a field.

data "aws_caller_identity" "current" {}

locals {
  templates_dir = "${path.module}/../../../../server/app/modules/ddl_commands/bulk_templates"
  templates     = toset(["buyer-template.csv", "seller-template.csv"])
}

resource "aws_s3_bucket" "assets" {
  bucket        = "${var.project}-assets-${data.aws_caller_identity.current.account_id}"
  force_destroy = false
}

# Public read comes only from the bucket policy below. ACLs stay blocked.
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
