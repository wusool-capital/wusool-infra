# stacks/base — prod
project     = "wusool"
environment = "prod"
aws_region  = "eu-central-1"

vpc_cidr                     = "10.20.0.0/16"
public_subnet_cidr           = "10.20.1.0/24"
private_subnet_cidr          = "10.20.2.0/24"
database_private_subnet_cidr = "10.20.3.0/24"

alert_email = "raoof@azmora.ai"
