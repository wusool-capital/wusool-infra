# Dev RDS Connection Runbook

The `wusool_crm` database is private inside the dev VPC. Connect through the
existing n8n EC2 instance with Systems Manager port forwarding.

## Open Tunnel

Run from `terraform/environments/dev`:

```powershell
$n8nInstanceId = terraform output -raw n8n_instance_id
$dbHost = (terraform output -raw postgres_endpoint).Split(":")[0]

aws ssm start-session `
  --target $n8nInstanceId `
  --document-name AWS-StartPortForwardingSessionToRemoteHost `
  --parameters "host=$dbHost,portNumber=5432,localPortNumber=15432" `
  --region eu-central-1
```

Keep this terminal open.

## Build DATABASE_URL

Run from the repository root:

```powershell
$secretArn = terraform -chdir=".\terraform\environments\dev" output -raw postgres_master_user_secret_arn
$secret = aws secretsmanager get-secret-value `
  --secret-id $secretArn `
  --query SecretString `
  --output text `
  --region eu-central-1 | ConvertFrom-Json

$user = [System.Uri]::EscapeDataString($secret.username)
$pass = [System.Uri]::EscapeDataString($secret.password)
$env:DATABASE_URL = "postgresql://${user}:${pass}@localhost:15432/wusool_crm?sslmode=require"
```

## Set Up and Sync

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\db\setup-postgres.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\db\sync-postgres.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\db\sync-postgres.ps1 -Apply
```

## Client

Both commands use Python `psycopg`; local `psql` and Docker are not required.
