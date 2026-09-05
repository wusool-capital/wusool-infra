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
      Scope     = "peering"
      ManagedBy = "terraform"
      Owner     = var.owner
    }
  }
}

data "terraform_remote_state" "base_dev" {
  backend = "s3"
  config = {
    bucket = "wusool-tfstate"
    key    = "wusool/dev/base/terraform.tfstate"
    region = "me-central-1"
  }
}

data "terraform_remote_state" "base_prod" {
  backend = "s3"
  config = {
    bucket = "wusool-tfstate"
    key    = "wusool/prod/base/terraform.tfstate"
    region = "me-central-1"
  }
}
