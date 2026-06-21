terraform {
  backend "s3" {
    bucket         = "wusool-tfstate"
    key            = "wusool/prod/terraform.tfstate"
    region         = "me-central-1"
    dynamodb_table = "wusool-tfstate-locks"
    encrypt        = true
  }
}
