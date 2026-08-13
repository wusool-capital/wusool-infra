output "state_bucket_name" {
  description = "S3 bucket name for Terraform remote state."
  value       = aws_s3_bucket.tfstate.id
}

output "lock_table_name" {
  description = "DynamoDB table name for Terraform state locking."
  value       = aws_dynamodb_table.tfstate_locks.name
}

output "aws_region" {
  description = "AWS region where the backend resources were created."
  value       = var.aws_region
}
