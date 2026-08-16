# All resources previously in this root have been migrated to terraform/stacks/
# via `state mv` (Phase D): network/CloudTrail/SNS -> stacks/base, n8n ->
# stacks/n8n, ECR + the wusool-toolkit secret -> stacks/toolkit (the toolkit EC2
# instance itself is not yet created — see stacks/toolkit's create_instance
# variable), postgres -> stacks/postgres. This root is intentionally empty and
# kept only until CI/CD workflows are retargeted at stacks/*, at which point it
# and terraform/environments/ are deleted entirely.
#
# These remote_state reads remain only because outputs.tf still surfaces
# convenience values (URLs, IDs) sourced from each stack.

data "terraform_remote_state" "base" {
  backend = "s3"
  config = {
    bucket = "wusool-tfstate"
    key    = "wusool/prod/base/terraform.tfstate"
    region = "me-central-1"
  }
}

data "terraform_remote_state" "n8n" {
  backend = "s3"
  config = {
    bucket = "wusool-tfstate"
    key    = "wusool/prod/n8n/terraform.tfstate"
    region = "me-central-1"
  }
}

data "terraform_remote_state" "toolkit" {
  backend = "s3"
  config = {
    bucket = "wusool-tfstate"
    key    = "wusool/prod/toolkit/terraform.tfstate"
    region = "me-central-1"
  }
}

data "terraform_remote_state" "postgres" {
  backend = "s3"
  config = {
    bucket = "wusool-tfstate"
    key    = "wusool/prod/postgres/terraform.tfstate"
    region = "me-central-1"
  }
}
