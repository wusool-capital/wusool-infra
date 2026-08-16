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
