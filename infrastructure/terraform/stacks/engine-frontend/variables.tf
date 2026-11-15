variable "cloudflare_account_id" {
  description = "Cloudflare account that owns the wusoolcapital.com zone and the Access identity provider."
  type        = string
  default     = "aa28a40954cce378e48680c2b5588dda"
}

variable "hostname" {
  description = "Public hostname of the Engine Worker. Must match the custom-domain route in engine-frontend/wrangler.jsonc."
  type        = string
  default     = "engine-dev.wusoolcapital.com"
}

variable "allowed_email_domains" {
  description = "Only addresses at these domains can sign in. The team's mail is on both while it moves."
  type        = list(string)
  default     = ["wusoolcapital.com", "dopaminecap.com"]

  validation {
    condition     = length(var.allowed_email_domains) > 0
    error_message = "At least one domain must be allowed, or nobody can sign in."
  }
}

variable "identity_provider_id" {
  description = "Existing one-time-PIN identity provider in the account; Access sends the code by email."
  type        = string
  default     = "a1130fe7-5039-40c1-bb37-1fd3467b69de"
}

variable "session_duration" {
  description = "How long a sign-in lasts before the next one-time PIN."
  type        = string
  default     = "24h"
}

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

variable "github_repo" {
  description = "owner/repo trusted by the engine deploy OIDC role."
  type        = string
  default     = "wusool-capital/wusool-infra"
}
