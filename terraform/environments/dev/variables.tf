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
  default     = "dev"
}

variable "bedrock_models" {
  description = "Bedrock foundation models to grant the n8n instance invoke access to."
  type = list(object({
    model_id             = string
    region               = string
    inference_profile_id = optional(string)
  }))
  default = [
    { model_id = "anthropic.claude-sonnet-4-6", region = "eu-central-1", inference_profile_id = "eu.anthropic.claude-sonnet-4-6" },
    { model_id = "anthropic.claude-haiku-4-5-20251001-v1:0", region = "eu-central-1", inference_profile_id = "eu.anthropic.claude-haiku-4-5-20251001-v1:0" },
    { model_id = "qwen.qwen3-235b-a22b-2507-v1:0", region = "eu-central-1" },
  ]
}

variable "vpc_cidr" {
  description = "Development VPC CIDR."
  type        = string
  default     = "10.10.0.0/16"
}

variable "public_subnet_cidr" {
  description = "Development public subnet CIDR."
  type        = string
  default     = "10.10.1.0/24"
}

variable "private_subnet_cidr" {
  description = "Development private subnet CIDR."
  type        = string
  default     = "10.10.2.0/24"
}

variable "database_private_subnet_cidr" {
  description = "Development second private subnet CIDR for RDS PostgreSQL."
  type        = string
  default     = "10.10.3.0/24"
}

variable "key_name" {
  description = "Existing EC2 key pair name for SSH access."
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type for development n8n."
  type        = string
  default     = "t3.small"
}

variable "ami_architecture" {
  description = "CPU architecture for the development n8n AMI."
  type        = string
  default     = "x86_64"
}

variable "root_volume_size" {
  description = "Root EBS volume size in GiB."
  type        = number
  default     = 30
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
  default     = true
}

variable "n8n_webhook_url" {
  description = "Optional public HTTPS URL for n8n. Empty derives an sslip.io hostname from the Elastic IP."
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

variable "postgres_db_name" {
  description = "Initial PostgreSQL database name for the CRM machine layer."
  type        = string
  default     = "wusool_crm"
}

variable "postgres_master_username" {
  description = "RDS PostgreSQL master username."
  type        = string
  default     = "wusool_admin"
}

variable "postgres_engine_version" {
  description = "RDS PostgreSQL engine version."
  type        = string
  default     = "16"
}

variable "postgres_instance_class" {
  description = "RDS PostgreSQL instance class for development."
  type        = string
  default     = "db.t4g.micro"
}

variable "postgres_allocated_storage" {
  description = "Allocated PostgreSQL storage in GiB."
  type        = number
  default     = 20
}

variable "wusool_toolkit_instance_type" {
  description = "EC2 instance type for the wusool-toolkit app. t2.micro is AWS Free Tier eligible."
  type        = string
  default     = "t2.micro"
}

variable "wusool_toolkit_public_url" {
  description = "Optional public HTTPS URL for the wusool-toolkit app (used as the Slack Request URL host). Empty derives an sslip.io hostname from its Elastic IP."
  type        = string
  default     = ""
}

variable "wusool_toolkit_git_repo_url" {
  description = "HTTPS clone URL of the repo containing the wusool-toolkit app."
  type        = string
  default     = "https://github.com/wusool-capital/wusool-infra.git"
}

variable "wusool_toolkit_git_ref" {
  description = "Branch or tag of wusool_toolkit_git_repo_url to deploy. MUST be an integration branch that actually contains workflows/wusool-toolkit/ - the stale `main` branch does not, and cloning it makes the bootstrap fail with a missing .env.production path."
  type        = string
  default     = "dev"
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
