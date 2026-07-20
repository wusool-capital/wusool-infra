param(
  [string]$DevApiKey = $env:DEV_ATTIO_API_KEY,
  [string]$DatabaseUrl = $env:DATABASE_URL,
  [string]$OutputDir = (Join-Path (Resolve-Path ".").Path "outputs\postgres-sync"),
  [int]$Limit = 500,
  [switch]$Apply
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($DevApiKey)) {
  throw "Missing DEV_ATTIO_API_KEY."
}

if ($Apply -and [string]::IsNullOrWhiteSpace($DatabaseUrl)) {
  throw "Missing DATABASE_URL."
}

$headers = @{
  Authorization  = "Bearer $DevApiKey"
  Accept         = "application/json"
  "Content-Type" = "application/json"
}

function Invoke-AttioPost {
  param([string]$Path, [object]$Body)

  Invoke-RestMethod `
    -Method Post `
    -Uri "https://api.attio.com/v2$Path" `
    -Headers $headers `
    -Body ([System.Text.Encoding]::UTF8.GetBytes(($Body | ConvertTo-Json -Depth 100)))
}

function Get-FirstValue {
  param([object]$Values, [string]$Slug)
  $items = @($Values.$Slug)
  if ($items.Count -eq 0) { return $null }
  return $items[0].value
}

function Get-FirstEmail {
  param([object]$Values)
  $items = @($Values.email_addresses)
  if ($items.Count -eq 0) { return $null }
  return $items[0].email_address
}

function ConvertTo-JsonText {
  param([object]$Value)
  if ($null -eq $Value) { return $null }
  return ($Value | ConvertTo-Json -Depth 100 -Compress)
}

function Get-CompanyLegacyByDevIdMap {
  $map = @{}
  $offset = 0
  while ($true) {
    $result = Invoke-AttioPost -Path "/objects/companies/records/query" -Body @{ limit = $Limit; offset = $offset }
    $records = @($result.data)
    foreach ($record in $records) {
      $legacyId = Get-FirstValue -Values $record.values -Slug "legacy_attio_id"
      if (-not [string]::IsNullOrWhiteSpace($legacyId)) {
        $map[$record.id.record_id] = $legacyId
      }
    }
    if ($records.Count -lt $Limit) { break }
    $offset += $Limit
  }
  return $map
}

New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

$companyLegacyByDevId = Get-CompanyLegacyByDevIdMap
$rows = @()
$offset = 0

while ($true) {
  Write-Host "Reading DEV people offset=$offset"
  $result = Invoke-AttioPost -Path "/objects/people/records/query" -Body @{ limit = $Limit; offset = $offset }
  $records = @($result.data)

  foreach ($record in $records) {
    $values = $record.values
    $legacyId = Get-FirstValue -Values $values -Slug "legacy_attio_id"
    if ([string]::IsNullOrWhiteSpace($legacyId)) { continue }

    $name = Get-FirstValue -Values $values -Slug "name"
    if ([string]::IsNullOrWhiteSpace($name)) {
      $name = "Unknown Source Person $legacyId"
    }

    $companyLegacyId = $null
    $companyRef = @($values.company) | Select-Object -First 1
    if ($companyRef -and $companyRef.target_record_id -and $companyLegacyByDevId.ContainsKey($companyRef.target_record_id)) {
      $companyLegacyId = $companyLegacyByDevId[$companyRef.target_record_id]
    }

    $email = Get-FirstEmail -Values $values
    $emailArray = @()
    if (-not [string]::IsNullOrWhiteSpace($email)) {
      $emailArray = @($email)
    }

    $rows += [pscustomobject]@{
      attio_id          = $legacyId
      name              = $name
      company_attio_id  = $companyLegacyId
      email_json        = ConvertTo-JsonText -Value $emailArray
      linkedin          = Get-FirstValue -Values $values -Slug "linkedin"
      role              = Get-FirstValue -Values $values -Slug "job_title"
      raw_attio_json    = ConvertTo-JsonText -Value $record
    }
  }

  if ($records.Count -lt $Limit) { break }
  $offset += $Limit
}

$csvPath = Join-Path $OutputDir "people.csv"
$sqlPath = Join-Path $OutputDir "sync-people.sql"
$rows | Export-Csv -Path $csvPath -NoTypeInformation -Encoding utf8

$sql = @'
CREATE TEMP TABLE stg_people (
  attio_id text,
  name text,
  company_attio_id text,
  email_json text,
  linkedin text,
  role text,
  raw_attio_json text
);

\copy stg_people FROM '/sync/people.csv' WITH (FORMAT csv, HEADER true, NULL '');

CREATE OR REPLACE FUNCTION pg_temp.jsonb_text_array(value jsonb)
RETURNS text[]
LANGUAGE sql
AS $$
  SELECT CASE
    WHEN value IS NULL THEN '{}'::text[]
    WHEN jsonb_typeof(value) = 'array' THEN COALESCE(ARRAY(SELECT jsonb_array_elements_text(value)), '{}'::text[])
    WHEN jsonb_typeof(value) = 'string' THEN ARRAY[value #>> '{}']
    ELSE '{}'::text[]
  END
$$;

INSERT INTO people (
  attio_id,
  name,
  company_attio_id,
  email,
  linkedin,
  role,
  raw_attio,
  updated_at
)
SELECT
  attio_id,
  name,
  company_attio_id,
  pg_temp.jsonb_text_array(COALESCE(NULLIF(email_json, '')::jsonb, '[]'::jsonb)),
  linkedin,
  role,
  COALESCE(NULLIF(raw_attio_json, '')::jsonb, '{}'::jsonb),
  now()
FROM stg_people
ON CONFLICT (attio_id) DO UPDATE SET
  name = EXCLUDED.name,
  company_attio_id = EXCLUDED.company_attio_id,
  email = EXCLUDED.email,
  linkedin = EXCLUDED.linkedin,
  role = EXCLUDED.role,
  raw_attio = EXCLUDED.raw_attio,
  updated_at = now();
'@

Set-Content -Path $sqlPath -Value $sql -Encoding utf8

Write-Host "Prepared $($rows.Count) people."
Write-Host "Wrote $csvPath"
Write-Host "Wrote $sqlPath"

if (-not $Apply) {
  Write-Host "DRY RUN: add -Apply to load people into PostgreSQL."
  exit 0
}

$dockerDatabaseUrl = $DatabaseUrl.Replace("localhost:15432", "host.docker.internal:15432")
$mountPath = $OutputDir.Replace("\", "/")

docker run --rm `
  -e DATABASE_URL="$dockerDatabaseUrl" `
  -v "${mountPath}:/sync:ro" `
  postgres:16 `
  psql "$dockerDatabaseUrl" -v ON_ERROR_STOP=1 -f "/sync/sync-people.sql"

Write-Host "PostgreSQL people sync complete."
