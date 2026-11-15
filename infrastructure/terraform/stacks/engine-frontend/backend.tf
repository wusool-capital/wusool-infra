# Partial backend: one directory, one state. The Engine has a single
# Cloudflare deployment, not a per-environment one - same convention as
# stacks/scribe-updates and stacks/assets.
#
#   tofu init -reconfigure \
#     -backend-config=bucket=wusool-tfstate \
#     -backend-config=region=me-central-1 \
#     -backend-config=key=wusool/shared/engine-frontend/terraform.tfstate \
#     -backend-config=use_lockfile=true -backend-config=encrypt=true
terraform {
  backend "s3" {}
}
