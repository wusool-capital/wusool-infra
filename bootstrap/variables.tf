variable "aws_region" {
  description = "AWS region for the Terraform state backend."
  type        = string
  default     = "me-central-1"
}

variable "state_bucket_name" {
  description = "Name of the S3 bucket used for Terraform remote state."
  type        = string
  default     = "wusool-tfstate"
}

variable "lock_table_name" {
  description = "Name of the DynamoDB table used for Terraform state locking."
  type        = string
  default     = "wusool-tfstate-locks"
}
