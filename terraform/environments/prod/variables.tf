variable "aws_region" {
  description = "AWS region."
  type        = string
  default     = "eu-central-1"
}

variable "owner" {
  description = "Team or person responsible for these resources."
  type        = string
  default     = "wusool-infra"
}

variable "project" {
  description = "Project name used in tags and resource names."
  type        = string
  default     = "wusool"
}

variable "environment" {
  description = "Environment name used in tags and resource names."
  type        = string
  default     = "prod"
}

variable "vpc_cidr" {
  description = "Production VPC CIDR."
  type        = string
  default     = "10.20.0.0/16"
}

variable "public_subnet_cidr" {
  description = "Production public subnet CIDR."
  type        = string
  default     = "10.20.1.0/24"
}

variable "private_subnet_cidr" {
  description = "Production private subnet CIDR."
  type        = string
  default     = "10.20.2.0/24"
}

variable "key_name" {
  description = "Existing EC2 key pair name for SSH access."
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type for production n8n."
  type        = string
  default     = "t3.small"
}

variable "ami_architecture" {
  description = "CPU architecture for the production n8n AMI."
  type        = string
  default     = "x86_64"

  validation {
    condition     = contains(["x86_64", "arm64"], var.ami_architecture)
    error_message = "ami_architecture must be x86_64 or arm64."
  }
}

variable "root_volume_size" {
  description = "Root EBS volume size in GiB."
  type        = number
  default     = 50
}

variable "ssh_cidr_blocks" {
  description = "CIDR blocks allowed to SSH into the n8n instance."
  type        = list(string)
}

variable "web_cidr_blocks" {
  description = "CIDR blocks allowed to reach HTTP/HTTPS and n8n."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "expose_n8n_port" {
  description = "Expose port 5678 publicly. Keep false when Caddy serves HTTPS."
  type        = bool
  default     = false
}

variable "n8n_webhook_url" {
  description = "Public webhook URL for n8n. Set to your HTTPS domain before apply."
  type        = string
  default     = ""
}

variable "n8n_timezone" {
  description = "Timezone for n8n."
  type        = string
  default     = "Asia/Dubai"
}

variable "alert_email" {
  description = "Email subscribed to infrastructure alerts; leave empty to skip subscription."
  type        = string
  default     = ""
}
