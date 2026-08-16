# try(..., null): these are null when create_instance = false (no instance
# exists yet — see the variable's description for why that is a real,
# deliberate state, not an error condition).

output "instance_id" {
  value = try(module.wusool_toolkit[0].instance_id, null)
}

output "public_ip" {
  value = try(module.wusool_toolkit[0].public_ip, null)
}

output "security_group_id" {
  value = try(module.wusool_toolkit[0].security_group_id, null)
}

output "iam_role_name" {
  value = try(module.wusool_toolkit[0].iam_role_name, null)
}

output "app_urls" {
  value = try(module.wusool_toolkit[0].app_urls, {})
}

output "ssm_instance_id" {
  value = try(module.wusool_toolkit[0].ssm_instance_id, null)
}

output "redeploy_command" {
  value = try(module.wusool_toolkit[0].redeploy_command, null)
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
