# Partial backend: one directory, one state. This stack publishes a single
# public update feed for one app, not a per-environment resource - same
# convention as stacks/account and stacks/peering.
#
#   tofu init -reconfigure \
#     -backend-config=bucket=wusool-tfstate \
#     -backend-config=region=me-central-1 \
#     -backend-config=key=wusool/shared/scribe-updates/terraform.tfstate \
#     -backend-config=use_lockfile=true -backend-config=encrypt=true
terraform {
  backend "s3" {}
}
