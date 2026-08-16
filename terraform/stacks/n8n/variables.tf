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

variable "key_name" {
  type        = string
  description = "EC2 key pair name. Empty disables SSH key access (use SSM instead)."
}

variable "instance_type" {
  type    = string
  default = "t3.small"
}

variable "ami_architecture" {
  type    = string
  default = "x86_64"
}

variable "root_volume_size" {
  type    = number
  default = 30
}

variable "ssh_cidr_blocks" {
  type    = list(string)
  default = []
}

variable "web_cidr_blocks" {
  type    = list(string)
  default = ["0.0.0.0/0"]
}

variable "expose_n8n_port" {
  type    = bool
  default = true
}

variable "n8n_webhook_url" {
  type    = string
  default = ""
}

variable "n8n_timezone" {
  type    = string
  default = "Asia/Dubai"
}

variable "n8n_additional_hostnames" {
  type    = list(string)
  default = []
}

variable "n8n_image" {
  description = "n8n image pinned by digest."
  type        = string
}

variable "runners_image" {
  description = "Task-runner image pinned by digest."
  type        = string
}

variable "caddy_image" {
  description = "Caddy image pinned by digest."
  type        = string
}

variable "enable_bedrock" {
  description = "Grant this n8n instance Bedrock invoke access. Prod does not use this yet."
  type        = bool
  default     = false
}

variable "bedrock_models" {
  description = "Bedrock foundation models to grant invoke access to, when enable_bedrock is true."
  type = list(object({
    model_id             = string
    region               = string
    inference_profile_id = optional(string)
  }))
  default = []
}

variable "alert_email" {
  type    = string
  default = ""
}
