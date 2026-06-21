module "network" {
  source = "../../modules/network"

  environment         = "prod"
  vpc_cidr            = var.vpc_cidr
  public_subnet_cidr  = var.public_subnet_cidr
  private_subnet_cidr = var.private_subnet_cidr
}

module "n8n" {
  source = "../../modules/n8n-ec2"

  environment      = "prod"
  vpc_id           = module.network.vpc_id
  subnet_id        = module.network.public_subnet_id
  key_name         = var.key_name
  instance_type    = var.instance_type
  ssh_cidr_blocks  = var.ssh_cidr_blocks
  web_cidr_blocks  = var.web_cidr_blocks
  expose_n8n_port  = var.expose_n8n_port
  n8n_webhook_url  = var.n8n_webhook_url
  n8n_timezone     = var.n8n_timezone
  root_volume_size = var.root_volume_size
}
