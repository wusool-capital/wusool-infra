# stacks/base — prod
project     = "wusool"
environment = "prod"
aws_region  = "eu-central-1"

vpc_cidr                     = "10.20.0.0/16"
public_subnet_cidr           = "10.20.1.0/24"
private_subnet_cidr          = "10.20.2.0/24"
database_private_subnet_cidr = "10.20.3.0/24"

alert_email = "raoof@azmora.ai"

# stacks/n8n — prod
key_name         = ""
instance_type    = "t3.small"
ami_architecture = "x86_64"
ssh_cidr_blocks  = []
web_cidr_blocks  = ["0.0.0.0/0"]
expose_n8n_port  = false
root_volume_size = 50
n8n_webhook_url  = "https://n8n.wusoolcapital.com/"
n8n_timezone     = "Asia/Dubai"
n8n_image        = "docker.n8n.io/n8nio/n8n@sha256:d53243d06c7f7de81910ac922ff55ed4b58c9c3c761d7f2f8443d0567990def3"
runners_image    = "n8nio/runners@sha256:dd8531c425cd2c60481cafcb145a8c810f628f176bcb8d41f4c75d79272f7d2a"
caddy_image      = "caddy@sha256:af5fdcd76f2db5e4e974ee92f96ee8c0fc3edb55bd4ba5032547cbf3f65e486d"
enable_bedrock   = false
