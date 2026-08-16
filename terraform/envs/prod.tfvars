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
key_name      = ""
instance_type = "t3.small"
ami_id        = "ami-0011111f781020765" # currently running on wusool-prod-n8n (H1)
# No prod toolkit instance exists yet (create_instance = false). This value is
# inert until that flips to true — review and set it deliberately at that point
# rather than trusting this placeholder.
toolkit_ami_id   = "ami-0ae7d073c75a47c24"
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

# stacks/toolkit — prod
# The instance does not exist yet. This creates only ECR + the secret
# container (already populated with real values — see prod matching-engine
# secret work), so the code is ready but a live prod compute instance is a
# deliberate, separate decision, not a side effect of this migration.
# key_name and enable_bedrock are shared with stacks/n8n above — same
# intended value, so not repeated here (a duplicate key is a parse error).
create_instance = false
public_url      = ""
