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

variable "slack_team_id" {
  description = "Slack workspace ID authorized for AWS Chatbot (Chatbot console -> Configured clients, after the one-time manual Slack authorization). Same value as stacks/base's identically-named variable — this is the account-wide, not per-environment, Chatbot relay."
  type        = string
  default     = "T0BAE254789"
}

variable "slack_channel_id" {
  description = "Slack channel ID AWS Chatbot posts infrastructure alerts to. Same value as stacks/base's identically-named variable."
  type        = string
  default     = "C0C0E16U0HH"
}
