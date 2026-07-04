terraform {
  backend "s3" {
    bucket       = "wusool-tfstate"
    key          = "wusool/dev/terraform.tfstate"
    region       = "me-central-1"
    use_lockfile = true
    encrypt      = true
  }
}
