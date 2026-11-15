terraform {
  required_version = ">= 1.12.0"
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5.29.0"
    }
  }
}

# The API token is read from CLOUDFLARE_API_TOKEN, never from a tfvars file.
provider "cloudflare" {}
