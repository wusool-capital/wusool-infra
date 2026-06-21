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
  description = "Name of an existing EC2 key pair for SSH access."
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type for n8n."
  type        = string
  default     = "t3.small"
}

variable "ami_architecture" {
  description = "CPU architecture of the Amazon Linux AMI (x86_64 or arm64)."
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
  description = "Expose port 5678 publicly until Nginx/ALB is configured."
  type        = bool
  default     = true
}

variable "n8n_webhook_url" {
  description = "Public webhook URL used by n8n (update after DNS/HTTPS is configured)."
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
