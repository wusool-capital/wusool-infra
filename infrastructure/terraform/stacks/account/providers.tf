terraform {
  required_version = ">= 1.12.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = var.project
      Scope     = "account"
      ManagedBy = "terraform"
      Owner     = var.owner
    }
  }
}

# The state bucket lives in me-central-1 (a deliberate, historical choice —
# state storage region is independent of where the resources it describes
# run). Every other resource in this stack uses the default eu-central-1
# provider; only the bucket resources below need this alias.
provider "aws" {
  alias  = "tfstate_bucket"
  region = "me-central-1"

  default_tags {
    tags = {
      Project   = var.project
      ManagedBy = "terraform"
      Scope     = "account"
    }
  }
}
