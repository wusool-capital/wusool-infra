output "vpc_id" {
  description = "Development VPC ID."
  value       = module.network.vpc_id
}

output "n8n_instance_id" {
  description = "Development n8n EC2 instance ID."
  value       = module.n8n.instance_id
}

output "n8n_public_ip" {
  description = "Elastic IP for the development n8n instance."
  value       = module.n8n.public_ip
}

output "n8n_url" {
  description = "Direct URL to access development n8n."
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
  value = aws_sns_topic.alerts.arn
}

output "n8n_secret_name" {
  description = "Secrets Manager secret name for development n8n."
  value       = aws_secretsmanager_secret.n8n.name
}

output "n8n_secret_arn" {
  description = "Secrets Manager secret ARN for development n8n."
  value       = aws_secretsmanager_secret.n8n.arn
}

output "postgres_endpoint" {
  description = "Private RDS PostgreSQL endpoint for the CRM machine layer."
  value       = module.postgres.endpoint
}

output "postgres_database_name" {
  description = "Initial PostgreSQL database name."
  value       = module.postgres.database_name
}

output "postgres_security_group_id" {
  description = "Security group attached to the private PostgreSQL instance."
  value       = module.postgres.security_group_id
}

output "postgres_master_user_secret_arn" {
  description = "Secrets Manager ARN containing the RDS managed master user password."
  value       = module.postgres.master_user_secret_arn
  sensitive   = true
}
