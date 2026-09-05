# Partial backend: one directory, one state. Account-level resources are NOT
# per-environment, so unlike the service stacks this has no dev/prod split.
#
#   tofu init -reconfigure \
#     -backend-config=bucket=wusool-tfstate \
#     -backend-config=region=me-central-1 \
#     -backend-config=key=wusool/account/terraform.tfstate \
#     -backend-config=use_lockfile=true -backend-config=encrypt=true
terraform {
  backend "s3" {}
}
