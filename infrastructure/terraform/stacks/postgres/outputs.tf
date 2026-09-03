output "endpoint" {
  value = module.postgres.endpoint
}

output "database_name" {
  value = module.postgres.database_name
}

output "security_group_id" {
  value = module.postgres.security_group_id
}

output "master_user_secret_arn" {
  value     = module.postgres.master_user_secret_arn
  sensitive = true
}
