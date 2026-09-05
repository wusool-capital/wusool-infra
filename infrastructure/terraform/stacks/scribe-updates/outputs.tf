output "updates_bucket_name" {
  value = aws_s3_bucket.updates.id
}

output "distribution_id" {
  value = aws_cloudfront_distribution.updates.id
}

output "distribution_domain_name" {
  value = aws_cloudfront_distribution.updates.domain_name
}

output "updater_endpoint" {
  description = "Paste into scribe-desktop/frontend/src-tauri/tauri.conf.json's plugins.updater.endpoints."
  value       = "https://${aws_cloudfront_distribution.updates.domain_name}/scribe/stable/latest.json"
}

output "release_role_arn" {
  description = "Not secret - safe to reference directly in workflow YAML, same convention as stacks/account's gha_role_arns."
  value       = aws_iam_role.gha_scribe_release.arn
}
