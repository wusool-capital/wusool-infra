variable "project" {
  description = "Project name used in resource names."
  type        = string
}

variable "environment" {
  description = "Environment name used in resource names."
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where PostgreSQL is deployed."
  type        = string
}

variable "subnet_ids" {
  description = "Private subnet IDs for the DB subnet group."
  type        = list(string)

  validation {
    condition     = length(var.subnet_ids) >= 2
    error_message = "RDS requires at least two private subnets in the DB subnet group."
  }
}

variable "allowed_security_group_ids" {
  description = "Security groups allowed to connect to PostgreSQL."
  type        = list(string)
}

variable "db_name" {
  description = "Initial database name."
  type        = string
  default     = "wusool_crm"
}

variable "master_username" {
  description = "RDS master username."
  type        = string
  default     = "wusool_admin"
}

variable "engine_version" {
  description = "PostgreSQL engine version."
  type        = string
  default     = "16"
}

variable "instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t4g.micro"
}

variable "allocated_storage" {
  description = "Allocated storage in GiB."
  type        = number
  default     = 20
}

variable "backup_retention_period" {
  description = "Automated backup retention in days."
  type        = number
  default     = 7
}

variable "deletion_protection" {
  description = "Protect the DB from accidental deletion."
  type        = bool
  default     = true
}

variable "skip_final_snapshot" {
  description = "Skip final snapshot on deletion."
  type        = bool
  default     = false
}

variable "snapshot_identifier" {
  description = <<-DESC
    Restore the instance from this DB snapshot instead of creating it empty.
    When set, db_name and username come FROM the snapshot and must not be sent —
    RDS rejects them, so the module omits both.

    Changing this on an existing instance forces replacement, which for a
    database means data loss. Set it once at creation and leave it alone.
  DESC
  type        = string
  default     = null
}
