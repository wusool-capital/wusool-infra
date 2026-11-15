# Cloudflare Access in front of the Engine Worker (static SPA, demo data).
# Own policy and application: nothing here references the advisors' team's
# existing Worker or Access app. Apply this BEFORE the first `wrangler deploy`
# so the hostname is never reachable without a sign-in.

resource "cloudflare_zero_trust_access_policy" "engine" {
  account_id = var.cloudflare_account_id
  name       = "wusool-engine-dev: ${join(", ", var.allowed_email_domains)} email"
  decision   = "allow"

  # One entry per domain: a visitor needs to match any of them.
  include = [for domain in var.allowed_email_domains : {
    email_domain = { domain = domain }
  }]
}

# The live Engine. It reuses the policy above, so one change to who may sign in covers both.
resource "cloudflare_zero_trust_access_application" "engine_prod" {
  account_id = var.cloudflare_account_id
  name       = "wusool-engine-prod"
  type       = "self_hosted"
  domain     = var.prod_hostname

  session_duration          = var.session_duration
  allowed_idps              = [var.identity_provider_id]
  auto_redirect_to_identity = true

  policies = [{
    id         = cloudflare_zero_trust_access_policy.engine.id
    precedence = 1
  }]
}

resource "cloudflare_zero_trust_access_application" "engine" {
  account_id = var.cloudflare_account_id
  name       = "wusool-engine-dev"
  type       = "self_hosted"
  domain     = var.hostname

  session_duration = var.session_duration
  allowed_idps     = [var.identity_provider_id]

  # One identity provider, so skip the picker and go straight to the email prompt.
  auto_redirect_to_identity = true

  policies = [{
    id         = cloudflare_zero_trust_access_policy.engine.id
    precedence = 1
  }]
}
