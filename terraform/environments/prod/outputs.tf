output "vpc_id" {
  description = "Production VPC ID."
  value       = module.network.vpc_id
}

output "n8n_instance_id" {
  description = "Production n8n EC2 instance ID."
  value       = module.n8n.instance_id
}

output "n8n_public_ip" {
  description = "Elastic IP for the production n8n instance."
  value       = module.n8n.public_ip
}

output "n8n_url" {
  description = "HTTPS URL served by Caddy for production n8n."
  value       = module.n8n.n8n_url
}

output "ssh_command" {
  description = "Example SSH command for the n8n instance."
  value       = "ssh -i ~/.ssh/${var.key_name}.pem ec2-user@${module.n8n.public_ip}"
}

output "ssm_command" {
  description = "Start a shell without opening SSH."
  value       = "aws ssm start-session --target ${module.n8n.ssm_instance_id} --region ${var.aws_region}"
}

output "alert_topic_arn" {
  description = "SNS topic receiving production infrastructure alerts."
  value       = aws_sns_topic.alerts.arn
}

output "n8n_secret_name" {
  description = "Secrets Manager secret name for production n8n."
  value       = aws_secretsmanager_secret.n8n.name
}

output "n8n_secret_arn" {
  description = "Secrets Manager secret ARN for production n8n."
  value       = aws_secretsmanager_secret.n8n.arn
}

output "postgres_endpoint" {
  description = "Production PostgreSQL endpoint. Verify any database_url in /wusool/prod/* points HERE and not at dev."
  value       = module.postgres.endpoint
}

output "postgres_database_name" {
  value = module.postgres.database_name
}

output "postgres_security_group_id" {
  description = "Consumers attach their own ingress rule referencing this SG."
  value       = module.postgres.security_group_id
}

output "postgres_master_user_secret_arn" {
  description = "RDS-managed master credential secret."
  value       = module.postgres.master_user_secret_arn
  sensitive   = true
}
