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

output "bedrock_model_arns" {
  description = "Bedrock foundation model ARNs the n8n instance role can invoke."
  value       = module.bedrock.model_arns
}

output "postgres_master_user_secret_arn" {
  description = "Secrets Manager ARN containing the RDS managed master user password."
  value       = module.postgres.master_user_secret_arn
  sensitive   = true
}

output "wusool_toolkit_instance_id" {
  description = "Development wusool-toolkit EC2 instance ID."
  value       = module.wusool_toolkit.instance_id
}

output "wusool_toolkit_public_ip" {
  description = "Elastic IP for the development wusool-toolkit instance."
  value       = module.wusool_toolkit.public_ip
}

output "wusool_toolkit_url" {
  description = "HTTPS URL for the wusool-toolkit app. Slack Request URLs are this plus /slack/events."
  value       = module.wusool_toolkit.app_urls["toolkit"]
}

output "wusool_toolkit_ssm_command" {
  description = "Start a shell on the wusool-toolkit instance without opening SSH."
  value       = "aws ssm start-session --target ${module.wusool_toolkit.ssm_instance_id} --region ${var.aws_region}"
}

output "wusool_toolkit_redeploy_command" {
  description = "Trigger a redeploy (git pull + rebuild + restart) without replacing the instance."
  value       = module.wusool_toolkit.redeploy_command
}

output "wusool_toolkit_secret_name" {
  description = "Secrets Manager secret name to populate with the wusool-toolkit runtime secrets."
  value       = aws_secretsmanager_secret.wusool_toolkit.name
}

output "wusool_toolkit_secret_arn" {
  description = "Secrets Manager secret ARN for the wusool-toolkit app."
  value       = aws_secretsmanager_secret.wusool_toolkit.arn
}

output "security_alert_topic_arn" {
  description = "Account-level SNS topic carrying GuardDuty and Security Hub findings."
  value       = aws_sns_topic.security_alerts.arn
}

output "wusool_toolkit_ecr_repository_url" {
  description = "Shared ECR repository. Both environments pull the same digests from here."
  value       = aws_ecr_repository.wusool_toolkit.repository_url
}
