# RDS Connection Runbook

The `wusool_crm` database is private inside its VPC. Connect through the
environment's n8n EC2 instance with Systems Manager port forwarding.

Works for either environment — substitute `dev` or `prod` for `<env>`
throughout. Everything below is read-only against Terraform state.

## 1. Read the instance and database endpoints

Each stack uses a partial backend, so `init` needs the environment's state key
(see `infrastructure/terraform/README.md`).

```powershell
$env:AWS_REGION = "eu-central-1"

# n8n stack -> the instance that has a network path to RDS
tofu -chdir=infrastructure/terraform/stacks/n8n init -reconfigure `
  -backend-config=bucket=wusool-tfstate `
  -backend-config=region=me-central-1 `
  -backend-config="key=wusool/<env>/n8n/terraform.tfstate" `
  -backend-config=use_lockfile=true -backend-config=encrypt=true
$n8nInstanceId = tofu -chdir=infrastructure/terraform/stacks/n8n output -raw instance_id

# postgres stack -> the database itself
tofu -chdir=infrastructure/terraform/stacks/postgres init -reconfigure `
  -backend-config=bucket=wusool-tfstate `
  -backend-config=region=me-central-1 `
  -backend-config="key=wusool/<env>/postgres/terraform.tfstate" `
  -backend-config=use_lockfile=true -backend-config=encrypt=true
$dbHost = (tofu -chdir=infrastructure/terraform/stacks/postgres output -raw endpoint).Split(":")[0]
$secretArn = tofu -chdir=infrastructure/terraform/stacks/postgres output -raw master_user_secret_arn
```

## 2. Open the tunnel

```powershell
aws ssm start-session `
  --target $n8nInstanceId `
  --document-name AWS-StartPortForwardingSessionToRemoteHost `
  --parameters "host=$dbHost,portNumber=5432,localPortNumber=15432" `
  --region eu-central-1
```

Keep that terminal open. Everything below runs in a second terminal.

## 3. Build DATABASE_URL

```powershell
$secret = aws secretsmanager get-secret-value `
  --secret-id $secretArn `
  --query SecretString --output text `
  --region eu-central-1 | ConvertFrom-Json

$user = [System.Uri]::EscapeDataString($secret.username)
$pass = [System.Uri]::EscapeDataString($secret.password)
$env:DATABASE_URL = "postgresql://${user}:${pass}@localhost:15432/wusool_crm?sslmode=require"
```

## 4. What to run through the tunnel

Schema changes go through Alembic, never a SQL file:

```powershell
cd server; uv run alembic upgrade head
```

For prod, the SOURCE Attio -> PostgreSQL sync and its validator:

```powershell
./prod/sync-all-to-prod.ps1            # dry run first, always
./prod/sync-all-to-prod.ps1 -Apply
./prod/validate-postgres.ps1
```

There is deliberately no dev equivalent — the dev database is a sandbox, not
a mirror of Attio. See this directory's README.

## Client

These scripts use Python `psycopg`; local `psql` and Docker are not required.
