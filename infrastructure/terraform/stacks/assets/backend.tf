# Partial backend: one directory, one state. This stack holds public download
# files, not a per-environment resource - same convention as stacks/account,
# stacks/peering and stacks/scribe-updates.
#
#   tofu init -reconfigure \
#     -backend-config=bucket=wusool-tfstate \
#     -backend-config=region=me-central-1 \
#     -backend-config=key=wusool/shared/assets/terraform.tfstate \
#     -backend-config=use_lockfile=true -backend-config=encrypt=true
terraform {
  backend "s3" {}
}
