#!/bin/bash
set -euxo pipefail

dnf update -y
dnf install -y amazon-ssm-agent
dnf install -y docker
dnf install -y amazon-cloudwatch-agent
dnf install -y awscli
dnf install -y jq
systemctl enable amazon-ssm-agent
systemctl restart amazon-ssm-agent
systemctl enable docker
systemctl start docker
usermod -aG docker ec2-user

mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "https://github.com/docker/compose/releases/download/v2.32.4/docker-compose-linux-$(uname -m)" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

mkdir -p /opt/toolkit/caddy

# Needed for the awslogs docker logging driver below - it has no equivalent
# of the CloudWatch agent's `{instance_id}` stream-name macro, so the real
# ID has to be baked into docker-compose.yml at generation time. IMDSv2
# token required: the instance's metadata_options enforce http_tokens =
# "required".
IMDS_TOKEN=$(curl -sX PUT "http://169.254.169.254/latest/api/token" \
  -H "X-aws-ec2-metadata-token-ttl-seconds: 60")
INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $IMDS_TOKEN" \
  http://169.254.169.254/latest/meta-data/instance-id)

# The instance is ASG-managed, not a standalone aws_instance with a static
# aws_eip_association — there is no stable instance ID for Terraform to
# attach the EIP to ahead of time. Every instance the ASG ever launches
# re-associates the one persistent EIP to itself here, on boot, so the
# public IP/hostname never changes across a replacement. --allow-reassociation
# is required: the EIP is still attached to whatever instance is being
# replaced until this runs.
aws ec2 associate-address --instance-id "$INSTANCE_ID" \
  --allocation-id "${eip_allocation_id}" --region "${aws_region}" --allow-reassociation

# set +x for the remainder: this script runs under `set -x`, and without this
# every secret below would be echoed verbatim into SSM command history (retained
# ~30 days) and CloudWatch. Re-enabling tracing after secret handling is not
# worth the leak risk, so tracing stays off from here.
set +x

# Login once, shared by every app - all apps pull from the same environment's
# ECR registry.
aws ecr get-login-password --region "${aws_region}" \
  | docker login --username AWS --password-stdin "${ecr_registry}"

# Each app has its own Secrets Manager secret, containing: slack_bot_token,
# slack_signing_secret, database_url, and optionally env: {} for extra
# overrides. github_token is no longer read here - nothing on this instance
# clones a repository.
#
# Note the ordering below: this block writes Terraform-derived defaults, then
# the `env: {}` passthrough is appended after it. Docker Compose's env_file is
# last-wins, so an operator can override any of these (ATTIO_IS_TEST included)
# via the secret without a `tofu apply` - while the default still comes from
# var.environment rather than from someone remembering to set it.
%{ for app in apps }
# --- ${app.name} ---
mkdir -p /opt/toolkit/${app.name}
SECRET_JSON_${app.slug}=$(aws secretsmanager get-secret-value --secret-id "${app.app_secret_id}" --region "${aws_region}" --query SecretString --output text)

cat > "/opt/toolkit/${app.name}/.env.production" <<ENVEOF
DATABASE_URL=$(echo "$SECRET_JSON_${app.slug}" | jq -r '.database_url // empty')
SLACK_BOT_TOKEN=$(echo "$SECRET_JSON_${app.slug}" | jq -r '.slack_bot_token // empty')
SLACK_SIGNING_SECRET=$(echo "$SECRET_JSON_${app.slug}" | jq -r '.slack_signing_secret // empty')
AWS_REGION=${aws_region}
ATTIO_IS_TEST=${attio_is_test}
ENVEOF
chmod 600 "/opt/toolkit/${app.name}/.env.production"

echo "$SECRET_JSON_${app.slug}" | jq -r '.env // {} | to_entries[] | "\(.key)=\(.value)"' >> "/opt/toolkit/${app.name}/.env.production"
chmod 600 "/opt/toolkit/${app.name}/.env.production"
%{ endfor }

cat > /opt/toolkit/caddy/Caddyfile <<CADDYEOF
%{ for app in apps }
${app.site_addresses} {
  # Compression belongs here rather than in the app: the lead-magnet tool
  # pages are ~750KB of static HTML, and a 1-vCPU Python process is the
  # wrong place to gzip them. Harmless for the Slack bot's small JSON.
  encode zstd gzip
  reverse_proxy ${app.name}:8000
  log {
    output file /data/${app.name}-access.log
  }
}
%{ endfor }
CADDYEOF

cat > /opt/toolkit/docker-compose.yml <<COMPOSEEOF
services:
%{ for app in apps }
  ${app.name}:
    image: ${app.image}
    restart: always
    expose:
      - "8000"
    env_file:
      - /opt/toolkit/${app.name}/.env.production
    logging:
      driver: awslogs
      options:
        awslogs-region: ${aws_region}
        awslogs-group: ${cloudwatch_log_group}
        awslogs-stream: $INSTANCE_ID/${app.name}
        awslogs-create-group: "true"
%{ endfor }
  caddy:
    image: caddy:2
    restart: always
    ports:
      - "80:80"
      - "443:443"
      - "443:443/udp"
    volumes:
      - /opt/toolkit/caddy/Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
  # Docker's own "restart: always" reacts only to a container EXITING — it
  # does nothing for a process that's still running but no longer answering
  # (a hung-but-alive uvicorn), even though the Dockerfile's own HEALTHCHECK
  # already detects exactly that and marks the container "unhealthy". Autoheal
  # is the piece that actually acts on that status: it watches every
  # container's health via the Docker socket and force-restarts any that go
  # unhealthy. This is the fix for the failure mode that motivated this
  # change — see the ASG module's main.tf comment on the 2026-09-09 incident.
  autoheal:
    image: willfarrell/autoheal:1.2.0
    restart: always
    environment:
      AUTOHEAL_CONTAINER_LABEL: all
      AUTOHEAL_INTERVAL: 30
    volumes:
      # NOT :ro — autoheal issues `docker restart` over this socket, which
      # needs write access; a read-only mount breaks that silently rather
      # than with an obvious permission error.
      - /var/run/docker.sock:/var/run/docker.sock

volumes:
  caddy_data:
  caddy_config:
COMPOSEEOF

cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json <<'CWEOF'
${cloudwatch_agent_config}
CWEOF
systemctl enable amazon-cloudwatch-agent
systemctl restart amazon-cloudwatch-agent

cd /opt/toolkit
docker compose pull

# `docker compose up -d`'s container-recreate sequence (stop old -> rename
# old to a temp name -> create new -> remove old) can transiently collide on
# the container name mid-recreate and exit non-zero even though the end
# state converges correctly a moment later (observed 2026-08-17: SSM
# reported the bootstrap Failed while the new container was already up and
# healthy). Retry once before treating it as a real failure - a false
# "Failed" here fails the whole CI deploy despite a successful rollout.
for attempt in 1 2 3; do
  if docker compose up -d; then
    break
  fi
  echo "docker compose up -d failed (attempt $attempt/3), retrying..." >&2
  sleep 5
  [ "$attempt" -eq 3 ] && exit 1
done
