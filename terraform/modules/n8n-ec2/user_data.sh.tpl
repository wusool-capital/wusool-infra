#!/bin/bash
set -euxo pipefail

dnf update -y
dnf install -y amazon-ssm-agent
dnf install -y docker
dnf install -y amazon-cloudwatch-agent
dnf install -y awscli
dnf install -y jq
dnf install -y openssl
systemctl enable amazon-ssm-agent
systemctl restart amazon-ssm-agent
systemctl enable docker
systemctl start docker
usermod -aG docker ec2-user

mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "https://github.com/docker/compose/releases/download/v2.32.4/docker-compose-linux-$(uname -m)" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

mkdir -p /opt/n8n
PRESERVED_RUNNERS_TOKEN=""
if [ -f /opt/n8n/n8n.env ]; then
  PRESERVED_RUNNERS_TOKEN=$(grep '^N8N_RUNNERS_AUTH_TOKEN=' /opt/n8n/n8n.env | head -1 | cut -d= -f2-)
fi

cat > /opt/n8n/n8n.env <<EOF
EOF
chmod 600 /opt/n8n/n8n.env

# The write above truncates n8n.env, which used to defeat the
# N8N_RUNNERS_AUTH_TOKEN guard further down and mint a new token on every
# bootstrap run. Capture any existing token first so re-running is idempotent.
# set +x from here: this script runs under `set -x`, so without this the SMTP
# credentials and every entry of the secret's env map would be echoed into SSM
# command history (retained ~30 days) and CloudWatch.
set +x

if [ -n "${n8n_secret_id}" ]; then
  if N8N_SECRET_JSON=$(aws secretsmanager get-secret-value --secret-id "${n8n_secret_id}" --query SecretString --output text 2>/dev/null); then
    SMTP_HOST=$(echo "$N8N_SECRET_JSON" | jq -r '.smtp_host // empty')
    if [ -n "$SMTP_HOST" ]; then
      {
        echo "N8N_EMAIL_MODE=smtp"
        echo "N8N_SMTP_HOST=$SMTP_HOST"
        echo "N8N_SMTP_PORT=$(echo "$N8N_SECRET_JSON" | jq -r '.smtp_port // 587')"
        echo "N8N_SMTP_USER=$(echo "$N8N_SECRET_JSON" | jq -r '.smtp_user // empty')"
        echo "N8N_SMTP_PASS=$(echo "$N8N_SECRET_JSON" | jq -r '.smtp_password // empty')"
        echo "N8N_SMTP_SENDER=$(echo "$N8N_SECRET_JSON" | jq -r '.smtp_sender // empty')"
        echo "N8N_SMTP_SSL=$(echo "$N8N_SECRET_JSON" | jq -r '.smtp_ssl // false')"
      } > /opt/n8n/n8n.env
      chmod 600 /opt/n8n/n8n.env
    fi

    echo "$N8N_SECRET_JSON" | jq -r '.env // {} | to_entries[] | "\(.key)=\(.value)"' >> /opt/n8n/n8n.env
    chmod 600 /opt/n8n/n8n.env
  fi
fi

if ! grep -q '^N8N_RUNNERS_AUTH_TOKEN=' /opt/n8n/n8n.env; then
  if [ -z "$PRESERVED_RUNNERS_TOKEN" ]; then
    PRESERVED_RUNNERS_TOKEN=$(openssl rand -hex 32)
  fi
  echo "N8N_RUNNERS_AUTH_TOKEN=$PRESERVED_RUNNERS_TOKEN" >> /opt/n8n/n8n.env
  chmod 600 /opt/n8n/n8n.env
fi

cat > /opt/n8n/n8n-task-runners.json <<EOF
{
	"task-runners": [
		{
			"runner-type": "javascript",
			"workdir": "/home/runner",
			"command": "/usr/local/bin/node",
			"args": [
				"--disallow-code-generation-from-strings",
				"--disable-proto=delete",
				"/opt/runners/task-runner-javascript/dist/start.js"
			],
			"health-check-server-port": "5681",
			"allowed-env": [
				"PATH",
				"GENERIC_TIMEZONE",
				"NODE_OPTIONS",
				"NODE_PATH",
				"N8N_RUNNERS_AUTO_SHUTDOWN_TIMEOUT",
				"N8N_RUNNERS_TASK_TIMEOUT",
				"N8N_RUNNERS_MAX_CONCURRENCY",
				"N8N_SENTRY_DSN",
				"N8N_VERSION",
				"ENVIRONMENT",
				"DEPLOYMENT_NAME",
				"HOME"
			],
			"env-overrides": {
				"NODE_FUNCTION_ALLOW_BUILTIN": "crypto",
				"NODE_FUNCTION_ALLOW_EXTERNAL": "moment",
				"N8N_RUNNERS_HEALTH_CHECK_SERVER_HOST": "0.0.0.0"
			}
		},
		{
			"runner-type": "python",
			"workdir": "/home/runner",
			"command": "/opt/runners/task-runner-python/.venv/bin/python",
			"args": ["-I", "-B", "-X", "disable_remote_debug", "-m", "src.main"],
			"health-check-server-port": "5682",
			"allowed-env": [
				"PATH",
				"N8N_RUNNERS_LAUNCHER_LOG_LEVEL",
				"N8N_RUNNERS_AUTO_SHUTDOWN_TIMEOUT",
				"N8N_RUNNERS_TASK_TIMEOUT",
				"N8N_RUNNERS_MAX_CONCURRENCY",
				"N8N_SENTRY_DSN",
				"N8N_VERSION",
				"ENVIRONMENT",
				"DEPLOYMENT_NAME",
				"N8N_RUNNERS_STDLIB_ALLOW",
				"N8N_RUNNERS_EXTERNAL_ALLOW",
				"N8N_BLOCK_RUNNER_ENV_ACCESS"
			],
			"env-overrides": {}
		}
	]
}
EOF

cat > /opt/n8n/docker-compose.yml <<EOF
services:
  n8n:
    image: ${n8n_image}
    restart: always
    expose:
      - "5678"
    environment:
      - N8N_HOST=${public_hostname}
      - N8N_PORT=5678
      - N8N_PROTOCOL=http
      - NODE_ENV=production
      - WEBHOOK_URL=${n8n_webhook_url}
      - GENERIC_TIMEZONE=${n8n_timezone}
      - N8N_RUNNERS_ENABLED=true
      - N8N_RUNNERS_MODE=external
      - N8N_RUNNERS_BROKER_LISTEN_ADDRESS=0.0.0.0
      - N8N_NATIVE_PYTHON_RUNNER=true
    env_file:
      - ./n8n.env
    volumes:
      - n8n_data:/home/node/.n8n
  task-runners:
    image: ${runners_image}
    restart: always
    environment:
      - N8N_RUNNERS_TASK_BROKER_URI=http://n8n:5679
      - N8N_NATIVE_PYTHON_RUNNER=true
      - N8N_RUNNERS_CONFIG_PATH=/etc/n8n-task-runners-custom.json
    env_file:
      - ./n8n.env
    volumes:
      - ./n8n-task-runners.json:/etc/n8n-task-runners-custom.json:ro
    depends_on:
      - n8n
  caddy:
    image: ${caddy_image}
    restart: always
    ports:
      - "80:80"
      - "443:443"
      - "443:443/udp"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config

volumes:
  n8n_data:
  caddy_data:
  caddy_config:
EOF

cat > /opt/n8n/Caddyfile <<EOF
${caddy_hostnames} {
  reverse_proxy n8n:5678
  log {
    output file /data/access.log
  }
}
EOF

cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json <<EOF
{
  "logs": {"logs_collected": {"files": {"collect_list": [
    {"file_path": "/var/log/cloud-init-output.log", "log_group_name": "${log_group_name}", "log_stream_name": "{instance_id}/cloud-init"},
    {"file_path": "/var/lib/docker/volumes/n8n_caddy_data/_data/access.log", "log_group_name": "${log_group_name}", "log_stream_name": "{instance_id}/caddy"}
  ]}}}
}
EOF
systemctl enable amazon-cloudwatch-agent
systemctl restart amazon-cloudwatch-agent

cd /opt/n8n

# `docker compose up -d`'s container-recreate sequence (stop old -> rename
# old to a temp name -> create new -> remove old) can transiently collide on
# the container name mid-recreate and exit non-zero even though the end
# state converges correctly a moment later (observed on toolkit's identical
# bootstrap 2026-08-17 - the same class of flakiness applies here). Retry
# once before treating it as a real failure - a false "Failed" here fails
# the whole CI deploy despite a successful rollout.
for attempt in 1 2 3; do
  if docker compose up -d; then
    break
  fi
  echo "docker compose up -d failed (attempt $attempt/3), retrying..." >&2
  sleep 5
  [ "$attempt" -eq 3 ] && exit 1
done
