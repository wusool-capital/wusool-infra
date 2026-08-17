variable "project" {
  description = "Project name used in resource names and log paths."
  type        = string
}

variable "environment" {
  description = "Environment name (dev, prod)."
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where the instance will be created."
  type        = string
}

variable "subnet_id" {
  description = "Subnet ID for the EC2 instance (public subnet for phase 1)."
  type        = string
}

variable "key_name" {
  description = "Name of an existing EC2 key pair for SSH access. Leave empty when using SSM only."
  type        = string
  default     = ""
}

variable "instance_type" {
  description = "EC2 instance type for n8n."
  type        = string
  default     = "t3.small"
}

variable "root_volume_size" {
  description = "Root EBS volume size in GiB."
  type        = number
  default     = 30
}

variable "ssh_cidr_blocks" {
  description = "CIDR blocks allowed to SSH into the instance."
  type        = list(string)
}

variable "web_cidr_blocks" {
  description = "CIDR blocks allowed to reach HTTP/HTTPS (and optionally n8n port)."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "expose_n8n_port" {
  description = "Expose port 5678 publicly. Keep false when Caddy serves HTTPS."
  type        = bool
  default     = true
}

variable "n8n_webhook_url" {
  description = "Public HTTPS URL used by n8n. When set, Caddy serves the URL hostname."
  type        = string
  default     = ""
}

variable "alarm_topic_arn" {
  description = "SNS topic ARN receiving EC2 alarms; empty disables alarm actions."
  type        = string
  default     = ""
}

variable "n8n_timezone" {
  description = "Timezone for n8n."
  type        = string
  default     = "Asia/Dubai"
}

variable "secrets_manager_secret_arns" {
  description = "Secrets Manager secret ARNs the n8n EC2 role can read."
  type        = list(string)
  default     = []
}

variable "n8n_secret_id" {
  description = "Secrets Manager secret ID containing optional n8n runtime settings such as SMTP configuration."
  type        = string
  default     = ""
}

variable "additional_hostnames" {
  description = <<-DESC
    Extra hostnames Caddy should serve alongside the primary hostname derived
    from n8n_webhook_url. Use during a domain cutover so the retired hostname
    keeps resolving until DNS has drained. Dropping a hostname here is what
    caused a prior production incident, so change with care.
  DESC
  type        = list(string)
  default     = []
}

variable "n8n_image" {
  description = "Fully-qualified n8n image, pinned by digest. Set per environment; no default, so an apply can never silently change the running version."
  type        = string

  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.n8n_image))
    error_message = "n8n_image must be pinned by digest (…@sha256:<64 hex>), not a mutable tag."
  }
}

variable "runners_image" {
  description = "Task-runner image, pinned by digest. n8nio/runners publishes no stable version tags — only 'latest' and nightlies, including a v3 line — so a tag pin could pull a v3 runner against a 2.x n8n."
  type        = string

  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.runners_image))
    error_message = "runners_image must be pinned by digest (…@sha256:<64 hex>), not a mutable tag."
  }
}

variable "caddy_image" {
  description = "Caddy image, pinned by digest."
  type        = string

  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.caddy_image))
    error_message = "caddy_image must be pinned by digest (…@sha256:<64 hex>), not a mutable tag."
  }
}

variable "ami_id" {
  description = "AMI to launch. Pinned explicitly (H1) — see main.tf's comment above the removed data source for why. Set this to the AMI currently running before changing anything else, then treat any change to it as a deliberate, reviewed upgrade."
  type        = string
}
