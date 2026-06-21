terraform {
  backend "s3" {
    bucket       = "wusool-tfstate-030179310793-eu-central-1"
    key          = "wusool/dev/terraform.tfstate"
    region       = "eu-central-1"
    use_lockfile = true
    encrypt      = true
  }
}
