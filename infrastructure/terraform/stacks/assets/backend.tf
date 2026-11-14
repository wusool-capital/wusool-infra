# Partial backend: one directory, one state, shared by both environments.

#   tofu init -reconfigure \
#     -backend-config=bucket=wusool-tfstate \
#     -backend-config=region=me-central-1 \
#     -backend-config=key=wusool/shared/assets/terraform.tfstate \
#     -backend-config=use_lockfile=true -backend-config=encrypt=true
terraform {
  backend "s3" {}
}
