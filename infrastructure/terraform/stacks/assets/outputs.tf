output "assets_bucket_name" {
  value = aws_s3_bucket.assets.id
}

output "templates_base_url" {
  description = "Set the toolkit secret's env key BULK_TEMPLATE_BASE_URL to this value (no trailing slash)."
  value       = "https://${aws_s3_bucket.assets.bucket_regional_domain_name}/templates"
}
