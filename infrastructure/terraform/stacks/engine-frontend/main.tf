# Cloudflare Access in front of the Engine Worker (static SPA, demo data).
# Own policy and application: nothing here references the advisors' team's
# existing Worker or Access app. Apply this BEFORE the first `wrangler deploy`
# so the hostname is never reachable without a sign-in.

resource "cloudflare_zero_trust_access_policy" "engine" {
  account_id = var.cloudflare_account_id
  name       = "wusool-engine-dev: ${var.allowed_email_domain} email"
  decision   = "allow"

  include = [{
    email_domain = { domain = var.allowed_email_domain }
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
