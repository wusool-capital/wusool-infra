terraform {
  backend "s3" {
    bucket       = "wusool-tfstate"
    key          = "wusool/prod/terraform.tfstate"
    region       = "me-central-1"
    use_lockfile = true
    encrypt      = true
  }
}
