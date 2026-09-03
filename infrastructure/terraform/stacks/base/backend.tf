# Partial backend — one directory serves both environments via -backend-config
# at init time. See envs/*.tfvars for how dev vs prod is selected.
terraform {
  backend "s3" {}
}
