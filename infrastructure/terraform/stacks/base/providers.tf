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

# Route 53 health check alarms are stricter than PutMetricAlarm's own docs
# suggest (learned the hard way, 2026-09-09): every ARN the alarm
# references — not just the alarm's own region — must be us-east-1, or
# PutMetricAlarm rejects it outright ("Invalid region eu-central-1
# specified. Only us-east-1 is supported."). So this alias exists for BOTH
# the alarm and the SNS topic it notifies, not just the alarm as originally
# assumed.
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
      Owner       = var.owner
    }
  }
}
