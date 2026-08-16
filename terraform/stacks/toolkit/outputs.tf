output "instance_id" {
  value = module.wusool_toolkit.instance_id
}

output "public_ip" {
  value = module.wusool_toolkit.public_ip
}

output "security_group_id" {
  value = module.wusool_toolkit.security_group_id
}

output "iam_role_name" {
  value = module.wusool_toolkit.iam_role_name
}

output "secret_name" {
  value = aws_secretsmanager_secret.wusool_toolkit.name
}

output "secret_arn" {
  value = aws_secretsmanager_secret.wusool_toolkit.arn
}

output "ecr_repository_url" {
  value = aws_ecr_repository.wusool_toolkit.repository_url
}

output "app_urls" {
  value = module.wusool_toolkit.app_urls
}

output "ssm_instance_id" {
  value = module.wusool_toolkit.ssm_instance_id
}

output "redeploy_command" {
  value = module.wusool_toolkit.redeploy_command
}
