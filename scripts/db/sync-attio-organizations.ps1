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
  param(
    [string]$Path,
    [object]$Body
  )

  Invoke-RestMethod `
    -Method Post `
    -Uri "https://api.attio.com/v2$Path" `
    -Headers $headers `
    -Body ([System.Text.Encoding]::UTF8.GetBytes(($Body | ConvertTo-Json -Depth 50)))
}

function Get-FirstValue {
  param(
    [object]$Values,
    [string]$Slug
  )

  $items = @($Values.$Slug)
  if ($items.Count -eq 0) {
    return $null
  }

  return $items[0].value
}

function Get-Domains {
  param([object]$Values)

  @($Values.domains) |
    Where-Object { $_.domain } |
    ForEach-Object { $_.domain }
}

function Get-SelectTitles {
  param(
    [object]$Values,
    [string]$Slug
  )

  @($Values.$Slug) |
    Where-Object { $_.option.title } |
    ForEach-Object { $_.option.title }
}

function ConvertTo-JsonText {
  param([object]$Value)

  if ($null -eq $Value) {
    return $null
  }

  return ($Value | ConvertTo-Json -Depth 100 -Compress)
}

New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

$rows = @()
$offset = 0

while ($true) {
  Write-Host "Reading DEV companies offset=$offset"
  $result = Invoke-AttioPost `
    -Path "/objects/companies/records/query" `
    -Body @{ limit = $Limit; offset = $offset }

  $records = @($result.data)
  foreach ($record in $records) {
    $values = $record.values
    $legacyId = Get-FirstValue -Values $values -Slug "legacy_attio_id"
    if ([string]::IsNullOrWhiteSpace($legacyId)) {
      continue
    }

    $name = Get-FirstValue -Values $values -Slug "name"
    if ([string]::IsNullOrWhiteSpace($name)) {
      $name = "Unknown Source Company $legacyId"
    }

    $rows += [pscustomobject]@{
      attio_id            = $legacyId
      name                = $name
      description         = Get-FirstValue -Values $values -Slug "description"
      domains_json        = ConvertTo-JsonText -Value @(Get-Domains -Values $values)
      categories_json     = ConvertTo-JsonText -Value @(Get-SelectTitles -Values $values -Slug "categories")
      type_json           = ConvertTo-JsonText -Value @(Get-SelectTitles -Values $values -Slug "type")
      sector_focus_json   = ConvertTo-JsonText -Value @(Get-SelectTitles -Values $values -Slug "sector_focus")
      raw_attio_json      = ConvertTo-JsonText -Value $record
    }
  }

  if ($records.Count -lt $Limit) {
    break
  }

  $offset += $Limit
}

$csvPath = Join-Path $OutputDir "organizations.csv"
$sqlPath = Join-Path $OutputDir "sync-organizations.sql"
$rows | Export-Csv -Path $csvPath -NoTypeInformation -Encoding utf8

$sql = @'
CREATE TEMP TABLE stg_organizations (
  attio_id text,
  name text,
  description text,
  domains_json text,
  categories_json text,
  type_json text,
  sector_focus_json text,
  raw_attio_json text
);

\copy stg_organizations FROM '/sync/organizations.csv' WITH (FORMAT csv, HEADER true, NULL '');

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

INSERT INTO organizations (
  attio_id,
  name,
  description,
  domains,
  categories,
  type,
  sector_focus,
  raw_attio,
  updated_at
)
SELECT
  attio_id,
  name,
  description,
  pg_temp.jsonb_text_array(COALESCE(NULLIF(domains_json, '')::jsonb, '[]'::jsonb)),
  pg_temp.jsonb_text_array(COALESCE(NULLIF(categories_json, '')::jsonb, '[]'::jsonb)),
  pg_temp.jsonb_text_array(COALESCE(NULLIF(type_json, '')::jsonb, '[]'::jsonb)),
  pg_temp.jsonb_text_array(COALESCE(NULLIF(sector_focus_json, '')::jsonb, '[]'::jsonb)),
  COALESCE(NULLIF(raw_attio_json, '')::jsonb, '{}'::jsonb),
  now()
FROM stg_organizations
ON CONFLICT (attio_id) DO UPDATE SET
  name = EXCLUDED.name,
  description = EXCLUDED.description,
  domains = EXCLUDED.domains,
  categories = EXCLUDED.categories,
  type = EXCLUDED.type,
  sector_focus = EXCLUDED.sector_focus,
  raw_attio = EXCLUDED.raw_attio,
  updated_at = now();
'@

Set-Content -Path $sqlPath -Value $sql -Encoding utf8

Write-Host "Prepared $($rows.Count) organizations."
Write-Host "Wrote $csvPath"
Write-Host "Wrote $sqlPath"

if (-not $Apply) {
  Write-Host "DRY RUN: add -Apply to load organizations into PostgreSQL."
  exit 0
}

$dockerDatabaseUrl = $DatabaseUrl.Replace("localhost:15432", "host.docker.internal:15432")
$mountPath = $OutputDir.Replace("\", "/")

docker run --rm `
  -e DATABASE_URL="$dockerDatabaseUrl" `
  -v "${mountPath}:/sync:ro" `
  postgres:16 `
  psql "$dockerDatabaseUrl" -v ON_ERROR_STOP=1 -f "/sync/sync-organizations.sql"

Write-Host "PostgreSQL organization sync complete."
