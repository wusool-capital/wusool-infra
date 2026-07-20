variable "project" {
  description = "Project name used in resource names."
  type        = string
}

variable "environment" {
  description = "Environment name (dev, prod)."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
}

variable "public_subnet_cidr" {
  description = "CIDR block for the public subnet."
  type        = string
}

variable "private_subnet_cidr" {
  description = "CIDR block for the private subnet."
  type        = string
}

variable "database_private_subnet_cidr" {
  description = "CIDR block for the second private subnet used by database subnet groups."
  type        = string
  default     = null
}

variable "private_subnet_az_index" {
  description = "Index of the available Availability Zone used by the private subnet."
  type        = number
  default     = 1

  validation {
    condition     = var.private_subnet_az_index >= 0
    error_message = "private_subnet_az_index must be zero or greater."
  }
}

variable "public_subnet_az_index" {
  description = "Index of the available Availability Zone used by the public subnet."
  type        = number
  default     = 0

  validation {
    condition     = var.public_subnet_az_index >= 0
    error_message = "public_subnet_az_index must be zero or greater."
  }
}

variable "database_private_subnet_az_index" {
  description = "Index of the available Availability Zone used by the second private database subnet."
  type        = number
  default     = 2

  validation {
    condition     = var.database_private_subnet_az_index >= 0
    error_message = "database_private_subnet_az_index must be zero or greater."
  }
}
