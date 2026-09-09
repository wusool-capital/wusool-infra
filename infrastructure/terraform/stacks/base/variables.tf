variable "project" {
  type    = string
  default = "wusool"
}

variable "environment" {
  type = string
}

variable "aws_region" {
  type    = string
  default = "eu-central-1"
}

variable "owner" {
  type    = string
  default = "wusool-infra"
}

variable "vpc_cidr" {
  type = string
}

variable "public_subnet_cidr" {
  type = string
}

variable "private_subnet_cidr" {
  type = string
}

variable "database_private_subnet_cidr" {
  type    = string
  default = null
}

variable "alert_email" {
  description = "Email subscribed to this environment's infrastructure alerts."
  type        = string
  default     = ""
}

variable "slack_team_id" {
  description = "Slack workspace ID authorized for AWS Chatbot (Chatbot console -> Configured clients, after the one-time manual Slack authorization). Same workspace for both environments."
  type        = string
  default     = ""
}

variable "slack_channel_id" {
  description = "Slack channel ID AWS Chatbot posts infrastructure alerts to. Same shared channel for both environments — the environment is already in each alarm's own name."
  type        = string
  default     = ""
}
