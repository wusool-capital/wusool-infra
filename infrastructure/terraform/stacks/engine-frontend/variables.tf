variable "cloudflare_account_id" {
  description = "Cloudflare account that owns the wusoolcapital.com zone and the Access identity provider."
  type        = string
  default     = "aa28a40954cce378e48680c2b5588dda"
}

variable "hostname" {
  description = "Public hostname of the Engine Worker. Must match the custom-domain route in engine/wrangler.jsonc."
  type        = string
  default     = "engine-dev.wusoolcapital.com"
}

variable "allowed_email_domain" {
  description = "Only addresses at this domain can sign in."
  type        = string
  default     = "wusoolcapital.com"
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
