variable "project" {
  description = "Project name used in resource naming."
  type        = string
}

variable "environment" {
  description = "Environment name used in resource naming."
  type        = string
}

variable "iam_role_name" {
  description = "Name of the existing IAM role to grant Bedrock model invoke permissions to."
  type        = string
}

variable "models" {
  description = "Foundation models to grant invoke access to. Each model is invoked in its own region, since Bedrock model availability varies by region. Set inference_profile_id for models that reject on-demand invocation and require a cross-region inference profile instead (Bedrock returns a ValidationException naming the required profile when this is the case)."
  type = list(object({
    model_id             = string
    region               = string
    inference_profile_id = optional(string)
  }))
}
