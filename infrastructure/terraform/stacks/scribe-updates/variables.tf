variable "project" {
  type    = string
  default = "wusool"
}

variable "aws_region" {
  type    = string
  default = "eu-central-1"
}

variable "owner" {
  type    = string
  default = "wusool-infra"
}

variable "cloudfront_price_class" {
  description = "PriceClass_200 (not the cheaper _100) because it includes the Middle East - the app's users are UAE-based."
  type        = string
  default     = "PriceClass_200"
}

variable "github_repo" {
  description = "owner/repo trusted by the release OIDC role."
  type        = string
  default     = "wusool-capital/wusool-infra"
}
