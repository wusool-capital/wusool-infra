param(
  [Parameter(Mandatory = $true)]
  [string]$InstanceId,
  [string]$Region = "eu-central-1"
)

$ErrorActionPreference = "Stop"

$commands = @(
  "set -euxo pipefail",
  "cd /opt/n8n",
  'sudo cp docker-compose.yml docker-compose.yml.bak.$(date +%Y%m%d%H%M%S)',
  'if ! sudo grep -q ''^N8N_RUNNERS_AUTH_TOKEN='' n8n.env; then echo "N8N_RUNNERS_AUTH_TOKEN=$(openssl rand -hex 32)" | sudo tee -a n8n.env >/dev/null; fi',
  "sudo chmod 600 n8n.env",
  'N8N_HOST_VALUE=$(sudo awk ''NR==1 {print $1; exit}'' Caddyfile)',
  'WEBHOOK_URL_VALUE="https://${N8N_HOST_VALUE}/"',
  'GENERIC_TIMEZONE_VALUE=$(sudo awk -F= ''/GENERIC_TIMEZONE=/{print $2; exit}'' docker-compose.yml)',
  'if [ -z "$GENERIC_TIMEZONE_VALUE" ]; then GENERIC_TIMEZONE_VALUE="Asia/Dubai"; fi',
  "sudo tee docker-compose.yml >/dev/null <<EOF",
  "services:",
  "  n8n:",
  "    image: docker.n8n.io/n8nio/n8n",
  "    restart: always",
  "    expose:",
  "      - ""5678""",
  "    environment:",
  '      - N8N_HOST=$N8N_HOST_VALUE',
  "      - N8N_PORT=5678",
  "      - N8N_PROTOCOL=http",
  "      - NODE_ENV=production",
  '      - WEBHOOK_URL=$WEBHOOK_URL_VALUE',
  '      - GENERIC_TIMEZONE=$GENERIC_TIMEZONE_VALUE',
  "      - N8N_RUNNERS_ENABLED=true",
  "      - N8N_RUNNERS_MODE=external",
  "      - N8N_RUNNERS_BROKER_LISTEN_ADDRESS=0.0.0.0",
  "      - N8N_NATIVE_PYTHON_RUNNER=true",
  "    env_file:",
  "      - ./n8n.env",
  "    volumes:",
  "      - n8n_data:/home/node/.n8n",
  "  task-runners:",
  "    image: n8nio/runners:latest",
  "    restart: always",
  "    environment:",
  "      - N8N_RUNNERS_TASK_BROKER_URI=http://n8n:5679",
  "      - N8N_NATIVE_PYTHON_RUNNER=true",
  "    env_file:",
  "      - ./n8n.env",
  "    depends_on:",
  "      - n8n",
  "  caddy:",
  "    image: caddy:2",
  "    restart: always",
  "    ports:",
  "      - ""80:80""",
  "      - ""443:443""",
  "      - ""443:443/udp""",
  "    volumes:",
  "      - ./Caddyfile:/etc/caddy/Caddyfile:ro",
  "      - caddy_data:/data",
  "      - caddy_config:/config",
  "",
  "volumes:",
  "  n8n_data:",
  "  caddy_data:",
  "  caddy_config:",
  "EOF",
  "sudo docker compose up -d",
  "sudo docker compose ps",
  "sudo docker compose logs --tail=80 task-runners"
)

$payloadPath = Join-Path $env:TEMP "n8n-enable-python-ssm-params.json"
@{
  commands = $commands
} | ConvertTo-Json -Compress | Set-Content -Path $payloadPath -Encoding ascii

$commandId = aws ssm send-command `
  --region $Region `
  --instance-ids $InstanceId `
  --document-name AWS-RunShellScript `
  --parameters "file://$payloadPath" `
  --query "Command.CommandId" `
  --output text

Write-Host "Started SSM command: $commandId"
Write-Host "Check status with:"
Write-Host "aws ssm get-command-invocation --region $Region --command-id $commandId --instance-id $InstanceId"
