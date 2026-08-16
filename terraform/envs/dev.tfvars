# stacks/base — dev
project     = "wusool"
environment = "dev"
aws_region  = "eu-central-1"

vpc_cidr                     = "10.10.0.0/16"
public_subnet_cidr           = "10.10.1.0/24"
private_subnet_cidr          = "10.10.2.0/24"
database_private_subnet_cidr = "10.10.3.0/24"

alert_email = "raoof@azmora.ai"

# stacks/n8n — dev
key_name        = "wusool-dev-frankfurt"
instance_type   = "t3.small"
ami_id          = "ami-0cb9c8280799ea859" # currently running on wusool-dev-n8n (H1)
toolkit_ami_id  = "ami-0ae7d073c75a47c24" # currently running on wusool-dev-toolkit (H1)
ssh_cidr_blocks = []
expose_n8n_port = false
n8n_webhook_url = "https://n8n-dev.wusoolcapital.com/"
n8n_timezone    = "Asia/Dubai"
n8n_image       = "docker.n8n.io/n8nio/n8n@sha256:0afb71a39e51637b4d5b4010d90e68bc502d3ca1d2a4d953eb5fcd7d86330ccd"
runners_image   = "n8nio/runners@sha256:dd8531c425cd2c60481cafcb145a8c810f628f176bcb8d41f4c75d79272f7d2a"
caddy_image     = "caddy@sha256:cfeb0b281bc44a5a51fecde39e9e577c60d863c0b6196e6bbdf58fd00960887f"
enable_bedrock  = true
bedrock_models = [
  { model_id = "anthropic.claude-sonnet-4-6", region = "eu-central-1", inference_profile_id = "eu.anthropic.claude-sonnet-4-6" },
  { model_id = "anthropic.claude-haiku-4-5-20251001-v1:0", region = "eu-central-1", inference_profile_id = "eu.anthropic.claude-haiku-4-5-20251001-v1:0" },
  { model_id = "qwen.qwen3-235b-a22b-2507-v1:0", region = "eu-central-1" },
]

# Pinned to the bare-IP hostname already in use (see the toolkit rename
# session) — leaving this empty would derive "toolkit-<ip>.sslip.io" and break
# the existing Slack Request URL. The IP is an Elastic IP; safe to hardcode.
public_url = "https://63-184-6-136.sslip.io"

# stacks/postgres — dev
# sg-0684b8cf83abfd065 = wusool-scribe-instance, a real cross-service
# dependency (scribe writes meetings via scribe_pub) — not junk.
extra_allowed_security_group_ids = ["sg-0684b8cf83abfd065"]
