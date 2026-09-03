# Partial backend: one directory, one state. This stack spans both
# environments (dev <-> prod peering), so unlike the service stacks it has no
# dev/prod split — same convention as stacks/account.
#
#   tofu init -reconfigure \
#     -backend-config=bucket=wusool-tfstate \
#     -backend-config=region=me-central-1 \
#     -backend-config=key=wusool/shared/peering/terraform.tfstate \
#     -backend-config=use_lockfile=true -backend-config=encrypt=true
terraform {
  backend "s3" {}
}
