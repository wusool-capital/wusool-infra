variable "project" {
  description = "Project name prefix."
  type        = string
  default     = "wusool"
}

variable "aws_region" {
  description = "Region for account-level resources. GuardDuty and Security Hub are per-account-per-region singletons, so this must match where the workloads run."
  type        = string
  default     = "eu-central-1"
}

variable "owner" {
  description = "Owner tag."
  type        = string
  default     = "platform"
}

variable "alert_email" {
  description = "Email subscribed to security findings. Leave empty to skip."
  type        = string
  default     = "raoof@azmora.ai"
}
