#!/bin/bash
set -euxo pipefail

dnf update -y
dnf install -y amazon-ssm-agent
dnf install -y docker
dnf install -y amazon-cloudwatch-agent
dnf install -y awscli
dnf install -y jq
dnf install -y git
systemctl enable amazon-ssm-agent
systemctl restart amazon-ssm-agent
systemctl enable docker
systemctl start docker
usermod -aG docker ec2-user

mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "https://github.com/docker/compose/releases/download/v2.32.4/docker-compose-linux-x86_64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

mkdir -p /opt/matching-engine/caddy
REPO_DIR=/opt/matching-engine/src

# `${app_secret_id}` is the Secrets Manager secret ID Terraform granted this
# instance's role read access to. It must contain: slack_bot_token,
# slack_signing_secret, database_url (pointing at the existing shared RDS
# instance), github_token (a fine-grained PAT with read-only access to
# `${git_repo_url}`), and optionally env: {} for extra overrides.
SECRET_JSON=$(aws secretsmanager get-secret-value --secret-id "${app_secret_id}" --region "${aws_region}" --query SecretString --output text)
GITHUB_TOKEN=$(echo "$SECRET_JSON" | jq -r '.github_token // empty')
SLACK_BOT_TOKEN=$(echo "$SECRET_JSON" | jq -r '.slack_bot_token // empty')
SLACK_SIGNING_SECRET=$(echo "$SECRET_JSON" | jq -r '.slack_signing_secret // empty')
DATABASE_URL=$(echo "$SECRET_JSON" | jq -r '.database_url // empty')

# The token is only ever embedded in the remote URL transiently, for the
# fetch/clone itself, then immediately swapped back to the plain URL so it
# never sits in `.git/config` in plaintext.
AUTH_REPO_URL=$(echo "${git_repo_url}" | sed "s#https://#https://x-access-token:$${GITHUB_TOKEN}@#")

if [ -d "$REPO_DIR/.git" ]; then
  git -C "$REPO_DIR" remote set-url origin "$AUTH_REPO_URL"
  git -C "$REPO_DIR" fetch --depth 1 origin "${git_ref}"
  git -C "$REPO_DIR" checkout "${git_ref}"
  git -C "$REPO_DIR" reset --hard "origin/${git_ref}"
  git -C "$REPO_DIR" remote set-url origin "${git_repo_url}"
else
  git clone --depth 1 --branch "${git_ref}" "$AUTH_REPO_URL" "$REPO_DIR"
  git -C "$REPO_DIR" remote set-url origin "${git_repo_url}"
fi

APP_DIR="$REPO_DIR/${app_subdir}"

cat > "$APP_DIR/.env.production" <<ENVEOF
DATABASE_URL=$DATABASE_URL
SLACK_BOT_TOKEN=$SLACK_BOT_TOKEN
SLACK_SIGNING_SECRET=$SLACK_SIGNING_SECRET
AWS_REGION=${aws_region}
ENVEOF
chmod 600 "$APP_DIR/.env.production"

echo "$SECRET_JSON" | jq -r '.env // {} | to_entries[] | "\(.key)=\(.value)"' >> "$APP_DIR/.env.production"
chmod 600 "$APP_DIR/.env.production"

cat > /opt/matching-engine/caddy/Caddyfile <<CADDYEOF
${public_hostname} {
  reverse_proxy app:8000
  log {
    output file /data/access.log
  }
}
CADDYEOF

cat > /opt/matching-engine/docker-compose.yml <<COMPOSEEOF
services:
  app:
    build: $APP_DIR
    restart: always
    expose:
      - "8000"
    env_file:
      - $APP_DIR/.env.production
  caddy:
    image: caddy:2
    restart: always
    ports:
      - "80:80"
      - "443:443"
      - "443:443/udp"
    volumes:
      - /opt/matching-engine/caddy/Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config

volumes:
  caddy_data:
  caddy_config:
COMPOSEEOF

cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json <<CWEOF
{
  "logs": {"logs_collected": {"files": {"collect_list": [
    {"file_path": "/var/log/cloud-init-output.log", "log_group_name": "${log_group_name}", "log_stream_name": "{instance_id}/cloud-init"},
    {"file_path": "/var/lib/docker/volumes/matching-engine_caddy_data/_data/access.log", "log_group_name": "${log_group_name}", "log_stream_name": "{instance_id}/caddy"}
  ]}}}
}
CWEOF
systemctl enable amazon-cloudwatch-agent
systemctl restart amazon-cloudwatch-agent

cd /opt/matching-engine
docker compose build
docker compose up -d
