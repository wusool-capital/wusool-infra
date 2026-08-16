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

variable "db_name" {
  type    = string
  default = "wusool_crm"
}

variable "master_username" {
  type    = string
  default = "wusool_admin"
}

variable "engine_version" {
  type    = string
  default = "16"
}

variable "instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "allocated_storage" {
  type    = number
  default = 20
}

variable "snapshot_identifier" {
  description = "Seed from this snapshot at creation. Set once, never changed afterward (module ignores subsequent changes)."
  type        = string
  default     = null
}

variable "extra_allowed_security_group_ids" {
  description = "Additional SGs to grant ingress, beyond n8n and toolkit (e.g. scribe's SG, currently hardcoded elsewhere)."
  type        = list(string)
  default     = []
}
