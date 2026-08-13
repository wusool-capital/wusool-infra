output "endpoint" {
  description = "RDS PostgreSQL endpoint."
  value       = aws_db_instance.this.endpoint
}

output "address" {
  description = "RDS PostgreSQL host address."
  value       = aws_db_instance.this.address
}

output "port" {
  description = "RDS PostgreSQL port."
  value       = aws_db_instance.this.port
}

output "database_name" {
  description = "Initial database name."
  value       = aws_db_instance.this.db_name
}

output "security_group_id" {
  description = "Security group attached to PostgreSQL."
  value       = aws_security_group.this.id
}

output "master_user_secret_arn" {
  description = "Secrets Manager ARN for the RDS managed master user password."
  value       = aws_db_instance.this.master_user_secret[0].secret_arn
}
