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

variable "database_private_subnet_cidr" {
  description = "Production database subnet CIDR. Mirrors dev's 10.10.3.0/24. Required before RDS can be created: the DB subnet group needs at least two subnets, and module.network returns compact([private, database_private])."
  type        = string
  default     = "10.20.3.0/24"
}

variable "postgres_db_name" {
  description = "Initial database name."
  type        = string
  default     = "wusool_crm"
}

variable "postgres_master_username" {
  description = "RDS master username. The password is RDS-managed (manage_master_user_password) and rotated automatically - never hand-write it."
  type        = string
  default     = "wusool_admin"
}

variable "postgres_engine_version" {
  description = "PostgreSQL engine version."
  type        = string
  default     = "16"
}

variable "postgres_instance_class" {
  description = "RDS instance class. db.t4g.micro is the cheapest Graviton burstable and matches dev."
  type        = string
  default     = "db.t4g.micro"
}

variable "postgres_allocated_storage" {
  description = "Allocated storage in GiB. Autoscales to 100 via the module's max_allocated_storage."
  type        = number
  default     = 20
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

variable "n8n_additional_hostnames" {
  description = "Extra hostnames Caddy should serve alongside the primary one. Used during a domain cutover."
  type        = list(string)
  default     = []
}

variable "n8n_image" {
  description = "n8n image pinned by digest. Set in terraform.tfvars from the digest currently running."
  type        = string
}

variable "runners_image" {
  description = "n8n task-runner image pinned by digest."
  type        = string
}

variable "caddy_image" {
  description = "Caddy image pinned by digest."
  type        = string
}

variable "postgres_snapshot_identifier" {
  description = "Dev snapshot to seed prod from. Set once at creation; changing it later would replace the instance and destroy its data (the module ignores subsequent changes)."
  type        = string
  default     = null
}
