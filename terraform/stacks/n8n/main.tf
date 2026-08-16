# n8n service — one stack, two states (dev/prod via envs/*.tfvars).
# Reads stacks/base for network + alarm topic. Migrated via `state mv` (Phase D).

resource "aws_secretsmanager_secret" "n8n" {
  name                    = "/${var.project}/${var.environment}/n8n"
  description             = "Environment-specific n8n secrets for ${var.project} ${var.environment}"
  recovery_window_in_days = 30
}

module "n8n" {
  source = "../../modules/n8n-ec2"

  project                     = var.project
  environment                 = var.environment
  vpc_id                      = data.terraform_remote_state.base.outputs.vpc_id
  subnet_id                   = data.terraform_remote_state.base.outputs.public_subnet_id
  key_name                    = var.key_name
  instance_type               = var.instance_type
  ami_architecture            = var.ami_architecture
  ssh_cidr_blocks             = var.ssh_cidr_blocks
  web_cidr_blocks             = var.web_cidr_blocks
  expose_n8n_port             = var.expose_n8n_port
  n8n_webhook_url             = var.n8n_webhook_url
  n8n_timezone                = var.n8n_timezone
  root_volume_size            = var.root_volume_size
  alarm_topic_arn             = data.terraform_remote_state.base.outputs.alarm_topic_arn
  secrets_manager_secret_arns = [aws_secretsmanager_secret.n8n.arn]
  n8n_secret_id               = aws_secretsmanager_secret.n8n.id
  additional_hostnames        = var.n8n_additional_hostnames
  n8n_image                   = var.n8n_image
  runners_image               = var.runners_image
  caddy_image                 = var.caddy_image
}

module "bedrock" {
  count  = var.enable_bedrock ? 1 : 0
  source = "../../modules/bedrock-access"

  project       = var.project
  environment   = var.environment
  iam_role_name = module.n8n.iam_role_name
  models        = var.bedrock_models
}
