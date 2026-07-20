param(
  [string]$DatabaseUrl = $env:DATABASE_URL,
  [string]$MigrationsPath = (Join-Path $PSScriptRoot "migrations")
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) {
  throw "Set DATABASE_URL or pass -DatabaseUrl. Example: postgresql://user:password@host:5432/wusool_crm?sslmode=require"
}

if (-not (Get-Command psql -ErrorAction SilentlyContinue)) {
  throw "psql was not found on PATH. Install PostgreSQL client tools before running migrations."
}

$migrationFiles = Get-ChildItem -Path $MigrationsPath -Filter "*.sql" | Sort-Object Name
if ($migrationFiles.Count -eq 0) {
  throw "No migration files found in $MigrationsPath"
}

foreach ($file in $migrationFiles) {
  Write-Host "Running migration $($file.Name)"
  psql $DatabaseUrl -v ON_ERROR_STOP=1 -f $file.FullName
}

Write-Host "Database migrations completed."
