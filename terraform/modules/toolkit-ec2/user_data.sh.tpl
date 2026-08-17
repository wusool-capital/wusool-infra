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
%{ for app in apps }
# --- ${app.name} ---
mkdir -p /opt/toolkit/${app.name}
SECRET_JSON_${app.slug}=$(aws secretsmanager get-secret-value --secret-id "${app.app_secret_id}" --region "${aws_region}" --query SecretString --output text)

cat > "/opt/toolkit/${app.name}/.env.production" <<ENVEOF
DATABASE_URL=$(echo "$SECRET_JSON_${app.slug}" | jq -r '.database_url // empty')
SLACK_BOT_TOKEN=$(echo "$SECRET_JSON_${app.slug}" | jq -r '.slack_bot_token // empty')
SLACK_SIGNING_SECRET=$(echo "$SECRET_JSON_${app.slug}" | jq -r '.slack_signing_secret // empty')
AWS_REGION=${aws_region}
ENVEOF
chmod 600 "/opt/toolkit/${app.name}/.env.production"

echo "$SECRET_JSON_${app.slug}" | jq -r '.env // {} | to_entries[] | "\(.key)=\(.value)"' >> "/opt/toolkit/${app.name}/.env.production"
chmod 600 "/opt/toolkit/${app.name}/.env.production"
%{ endfor }

cat > /opt/toolkit/caddy/Caddyfile <<CADDYEOF
%{ for app in apps }
${app.hostname} {
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
