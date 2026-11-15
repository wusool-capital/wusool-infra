output "hostname" {
  value = var.hostname
}

output "access_application_id" {
  value = cloudflare_zero_trust_access_application.engine.id
}

output "deploy_role_arn" {
  description = "Not secret - referenced directly in deploy-engine.yml."
  value       = aws_iam_role.gha_engine_deploy.arn
}

output "deploy_secret_name" {
  value = aws_secretsmanager_secret.cloudflare_deploy.name
}
