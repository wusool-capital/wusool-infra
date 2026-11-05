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

# The app reads its own secret from Secrets Manager at startup through the
# instance role, so no secret is written to disk. runtime.env holds only
# Terraform-owned, non-secret settings; process env outranks the secret, so
# APP_ENV and ATTIO_IS_TEST cannot drift through a stale secret edit.
#
# The host still fetches the secret into a shell variable, solely to hash the
# architecture viewer's Caddy password below. github_token is no longer read
# here - nothing on this instance clones a repository.
%{ for app in apps }
# --- ${app.name} ---
mkdir -p /opt/toolkit/${app.name}
SECRET_JSON_${app.slug}=$(aws secretsmanager get-secret-value --secret-id "${app.app_secret_id}" --region "${aws_region}" --query SecretString --output text)

cat > "/opt/toolkit/${app.name}/runtime.env" <<ENVEOF
APP_ENV=${app_env}
ATTIO_IS_TEST=${attio_is_test}
AWS_REGION=${aws_region}
AWS_SECRETS_MANAGER_SECRET_ID=${app.app_secret_id}
ENVEOF

# Superseded by the app's own secret fetch; remove the plaintext copy.
rm -f "/opt/toolkit/${app.name}/.env.production"
%{ endfor }

# The architecture viewer is protected by Caddy Basic Auth. The human-readable
# phrase is supplied through the existing Secrets Manager env map and is
# converted to Caddy's password hash format only on the instance.
ARCHITECTURE_BASIC_AUTH_PASSWORD=$(echo "$SECRET_JSON_toolkit" | jq -r '.env.ARCHITECTURE_BASIC_AUTH_PASSWORD // empty')
if [ -z "$ARCHITECTURE_BASIC_AUTH_PASSWORD" ]; then
  echo "ARCHITECTURE_BASIC_AUTH_PASSWORD is required for the protected architecture route" >&2
  exit 1
fi
docker pull caddy:2
ARCHITECTURE_BASIC_AUTH_HASH=$(docker run --rm caddy:2 caddy hash-password --plaintext "$ARCHITECTURE_BASIC_AUTH_PASSWORD")
unset ARCHITECTURE_BASIC_AUTH_PASSWORD SECRET_JSON_toolkit

cat > /opt/toolkit/caddy/Caddyfile <<CADDYEOF
%{ for app in apps }
${app.site_addresses} {
  # Compression belongs here rather than in the app: the lead-magnet tool
  # pages are ~750KB of static HTML, and a 1-vCPU Python process is the
  # wrong place to gzip them. Harmless for the Slack bot's small JSON.
  encode zstd gzip
  @architecture {
    path /architecture /architecture/*
  }
  handle @architecture {
    basic_auth {
      architecture $${ARCHITECTURE_BASIC_AUTH_HASH}
    }
    reverse_proxy ${app.name}:8000
  }
  handle {
    reverse_proxy ${app.name}:8000
  }
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
    # Reaps orphaned Chromium processes; PID 1 is Python and never waits on them.
    init: true
    # 2026-11-03: an uncapped Chromium starved the 2 GB host for an hour. Over the cap the
    # kernel kills Chromium in this cgroup, so dockerd, Caddy and the watchdog stay alive.
    # Equal swap limit stops it spilling to swap. Size from a measured PDF render peak.
    mem_limit: 1200m
    memswap_limit: 1200m
    expose:
      - "8000"
    env_file:
      - /opt/toolkit/${app.name}/runtime.env
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
    # Without this its restarts leave no trace once the container is recreated.
    logging:
      driver: awslogs
      options:
        awslogs-region: ${aws_region}
        awslogs-group: ${cloudwatch_log_group}
        awslogs-stream: $INSTANCE_ID/autoheal
        awslogs-create-group: "true"
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

# Host-level watchdog, outside Docker: autoheal only sees containers that Docker marks
# unhealthy, so it misses a stopped Caddy, a hung Caddy and a stalled dockerd. This probes
# /health through Caddy; 3 misses restart the stack, 3 more reboot (at most once an hour).
cat > /opt/toolkit/watchdog.sh <<'WDEOF'
#!/bin/bash
set -u
STATE=/run/toolkit-watchdog.failures
REBOOT_STAMP=/var/lib/toolkit-watchdog.reboot
log() { echo "$(date -u +%FT%TZ) toolkit_watchdog_action=$1 failures=$2" >> /var/log/toolkit-watchdog.log; }

failed=0
# Caddy has no localhost site, so resolve each hostname to this host to keep TLS valid.
for host in ${join(" ", [for app in apps : app.hostname])}; do
  curl -fsS -m 5 -o /dev/null --resolve "$host:443:127.0.0.1" "https://$host/health" || failed=1
done
if [ "$failed" -eq 0 ]; then
  rm -f "$STATE"
  exit 0
fi

n=$(( $(cat "$STATE" 2>/dev/null || echo 0) + 1 ))
echo "$n" > "$STATE"
cd /opt/toolkit
if [ "$n" -eq 3 ]; then
  log restart "$n"
  # `up -d` revives a stopped container; `restart` unwedges a running one.
  timeout 120 docker compose up -d
  timeout 120 docker compose restart
elif [ "$n" -ge 6 ] && { [ ! -e "$REBOOT_STAMP" ] || [ -n "$(find "$REBOOT_STAMP" -mmin +60)" ]; }; then
  log reboot "$n"
  touch "$REBOOT_STAMP"
  systemctl reboot
fi
WDEOF
chmod +x /opt/toolkit/watchdog.sh

cat > /etc/systemd/system/toolkit-watchdog.service <<'WDEOF'
[Unit]
Description=Restart the toolkit stack when /health stops answering through Caddy
After=docker.service

[Service]
Type=oneshot
ExecStart=/opt/toolkit/watchdog.sh
WDEOF

# OnBootSec gives Caddy time to get its certificates before the first probe.
cat > /etc/systemd/system/toolkit-watchdog.timer <<'WDEOF'
[Unit]
Description=Run the toolkit watchdog every 30 seconds

[Timer]
OnBootSec=10min
OnUnitActiveSec=30s
AccuracySec=1s

[Install]
WantedBy=timers.target
WDEOF
systemctl daemon-reload
systemctl enable --now toolkit-watchdog.timer

# Each deploy leaves its old image behind; on 2026-10-13 they filled the root
# disk and the next pull failed. ECR keeps every image for rollback.
docker image prune -af || true
