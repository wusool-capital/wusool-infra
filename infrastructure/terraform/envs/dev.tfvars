# stacks/base — dev
project     = "wusool"
environment = "dev"
aws_region  = "eu-central-1"

vpc_cidr                     = "10.10.0.0/16"
public_subnet_cidr           = "10.10.1.0/24"
private_subnet_cidr          = "10.10.2.0/24"
database_private_subnet_cidr = "10.10.3.0/24"

alert_email = "raoof@azmora.ai"

# AWS Chatbot -> #infra-alerts, shared with prod (workspace: Azmora)
slack_team_id    = "T0BAE254789"
slack_channel_id = "C0C0E16U0HH"

# stacks/toolkit — dev (shared network/bedrock settings)
key_name        = "wusool-dev-frankfurt"
toolkit_ami_id  = "ami-0ae7d073c75a47c24" # currently running on wusool-dev-toolkit (H1)
ssh_cidr_blocks = []
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

# stacks/toolkit — image pinned by digest (Phase F). Built and pushed by
# _build.yml; verified against ECR before pinning here.
image_digest = "sha256:ad9e212f7c868cda1dabd4bc1c41da068b6448b32c13219d4bf6198dc2f42da2"

# 2026-08-19: t2.micro hit InsufficientInstanceCapacity in eu-central-1a mid-
# deploy, leaving wusool-dev-toolkit stopped. Switched to the documented
# fallback (see toolkit-ec2/variables.tf's instance_type description) to
# unblock it — t3.micro's 1 GiB RAM and 10%-of-a-core baseline turned every
# deploy's image pull + `docker-compose` restart + migration container into
# a 13+ minute wait (vs. prod's t3.small: ~1 minute for the same steps,
# confirmed from actual deploy-dev.yml/deploy-prod.yml run timings).
# 2026-09-14: bumped to match prod's size — same fix without reintroducing
# the capacity risk t2.micro hit.
toolkit_instance_type = "t3.small"

# RDS-managed master secret for wusool-dev-postgres: the deploy migration step
# reads it for DDL, because the app itself only has a data-only login.
toolkit_db_master_secret_arn = "arn:aws:secretsmanager:eu-central-1:030179310793:secret:rds!db-e8bdd9d8-8f57-49c5-825a-6dc1f1416108-rF5A3x"
