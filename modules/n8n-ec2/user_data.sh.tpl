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
curl -SL "https://github.com/docker/compose/releases/download/v2.32.4/docker-compose-linux-x86_64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

mkdir -p /opt/n8n
cat > /opt/n8n/n8n.env <<EOF
EOF
chmod 600 /opt/n8n/n8n.env

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

cat > /opt/n8n/docker-compose.yml <<EOF
services:
  n8n:
    image: docker.n8n.io/n8nio/n8n
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
    env_file:
      - ./n8n.env
    volumes:
      - n8n_data:/home/node/.n8n
  caddy:
    image: caddy:2
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
${public_hostname} {
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
docker compose up -d
