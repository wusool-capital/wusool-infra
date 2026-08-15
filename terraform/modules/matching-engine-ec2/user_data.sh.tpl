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

# All apps share one clone of this repo. The github_token comes from the
# first app's secret (a repo-level credential, not an app-specific one) and
# is only ever embedded in the remote URL transiently, for the fetch/clone
# itself, then immediately swapped back to the plain URL so it never sits in
# `.git/config` in plaintext.
GITHUB_TOKEN=$(aws secretsmanager get-secret-value --secret-id "${github_secret_id}" --region "${aws_region}" --query SecretString --output text | jq -r '.github_token // empty')
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

# Each app has its own Secrets Manager secret, containing: slack_bot_token,
# slack_signing_secret, database_url, github_token (used only for the shared
# clone above), and optionally env: {} for extra overrides.
%{ for app in apps }
# --- ${app.name} ---
SECRET_JSON_${app.slug}=$(aws secretsmanager get-secret-value --secret-id "${app.app_secret_id}" --region "${aws_region}" --query SecretString --output text)
APP_DIR_${app.slug}="$REPO_DIR/${app.app_subdir}"

cat > "$APP_DIR_${app.slug}/.env.production" <<ENVEOF
DATABASE_URL=$(echo "$SECRET_JSON_${app.slug}" | jq -r '.database_url // empty')
SLACK_BOT_TOKEN=$(echo "$SECRET_JSON_${app.slug}" | jq -r '.slack_bot_token // empty')
SLACK_SIGNING_SECRET=$(echo "$SECRET_JSON_${app.slug}" | jq -r '.slack_signing_secret // empty')
AWS_REGION=${aws_region}
ENVEOF
chmod 600 "$APP_DIR_${app.slug}/.env.production"

echo "$SECRET_JSON_${app.slug}" | jq -r '.env // {} | to_entries[] | "\(.key)=\(.value)"' >> "$APP_DIR_${app.slug}/.env.production"
chmod 600 "$APP_DIR_${app.slug}/.env.production"
%{ endfor }

cat > /opt/matching-engine/caddy/Caddyfile <<CADDYEOF
%{ for app in apps }
${app.hostname} {
  reverse_proxy ${app.name}:8000
  log {
    output file /data/${app.name}-access.log
  }
}
%{ endfor }
CADDYEOF

cat > /opt/matching-engine/docker-compose.yml <<COMPOSEEOF
services:
%{ for app in apps }
  ${app.name}:
    build: $REPO_DIR/${app.app_subdir}
    restart: always
    expose:
      - "8000"
    env_file:
      - $REPO_DIR/${app.app_subdir}/.env.production
%{ endfor }
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

cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json <<'CWEOF'
${cloudwatch_agent_config}
CWEOF
systemctl enable amazon-cloudwatch-agent
systemctl restart amazon-cloudwatch-agent

cd /opt/matching-engine
docker compose build
docker compose up -d
