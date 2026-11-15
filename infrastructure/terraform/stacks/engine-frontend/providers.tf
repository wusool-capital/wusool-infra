terraform {
  required_version = ">= 1.12.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5.29.0"
    }
  }
}

# The API token is read from CLOUDFLARE_API_TOKEN, never from a tfvars file.
provider "cloudflare" {}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project   = var.project
      Scope     = "engine-frontend"
      ManagedBy = "terraform"
      Owner     = var.owner
    }
  }
}
