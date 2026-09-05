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
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
      Owner       = var.owner
    }
  }
}

data "terraform_remote_state" "base" {
  backend = "s3"
  config = {
    bucket = "wusool-tfstate"
    key    = "wusool/${var.environment}/base/terraform.tfstate"
    region = "me-central-1"
  }
}

data "terraform_remote_state" "n8n" {
  backend = "s3"
  config = {
    bucket = "wusool-tfstate"
    key    = "wusool/${var.environment}/n8n/terraform.tfstate"
    region = "me-central-1"
  }
}

data "terraform_remote_state" "toolkit" {
  backend = "s3"
  config = {
    bucket = "wusool-tfstate"
    key    = "wusool/${var.environment}/toolkit/terraform.tfstate"
    region = "me-central-1"
  }
}
