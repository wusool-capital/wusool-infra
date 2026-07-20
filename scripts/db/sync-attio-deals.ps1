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

function Get-FirstStatusTitle {
  param([object]$Values, [string]$Slug)
  $items = @($Values.$Slug)
  if ($items.Count -eq 0 -or -not $items[0].status.title) { return $null }
  return $items[0].status.title
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
  Write-Host "Reading DEV deals offset=$offset"
  $result = Invoke-AttioPost -Path "/objects/deals/records/query" -Body @{ limit = $Limit; offset = $offset }
  $records = @($result.data)

  foreach ($record in $records) {
    $values = $record.values
    $legacyId = Get-FirstValue -Values $values -Slug "legacy_attio_id"
    if ([string]::IsNullOrWhiteSpace($legacyId)) { continue }

    $name = Get-FirstValue -Values $values -Slug "name"
    if ([string]::IsNullOrWhiteSpace($name)) {
      $name = "Unknown Source Deal $legacyId"
    }

    $sellerLegacyId = $null
    $companyRef = @($values.associated_company) | Select-Object -First 1
    if ($companyRef -and $companyRef.target_record_id -and $companyLegacyByDevId.ContainsKey($companyRef.target_record_id)) {
      $sellerLegacyId = $companyLegacyByDevId[$companyRef.target_record_id]
    }

    $rows += [pscustomobject]@{
      attio_id                     = $legacyId
      name                         = $name
      stage                        = Get-FirstStatusTitle -Values $values -Slug "stage"
      seller_organization_attio_id = $sellerLegacyId
      raw_attio_json               = ConvertTo-JsonText -Value $record
    }
  }

  if ($records.Count -lt $Limit) { break }
  $offset += $Limit
}

$csvPath = Join-Path $OutputDir "deals.csv"
$sqlPath = Join-Path $OutputDir "sync-deals.sql"
$rows | Export-Csv -Path $csvPath -NoTypeInformation -Encoding utf8

$sql = @'
CREATE TEMP TABLE stg_deals (
  attio_id text,
  name text,
  stage text,
  seller_organization_attio_id text,
  raw_attio_json text
);

\copy stg_deals FROM '/sync/deals.csv' WITH (FORMAT csv, HEADER true, NULL '');

INSERT INTO deals (
  attio_id,
  name,
  stage,
  seller_organization_attio_id,
  raw_attio,
  updated_at
)
SELECT
  attio_id,
  name,
  stage,
  seller_organization_attio_id,
  COALESCE(NULLIF(raw_attio_json, '')::jsonb, '{}'::jsonb),
  now()
FROM stg_deals
ON CONFLICT (attio_id) DO UPDATE SET
  name = EXCLUDED.name,
  stage = EXCLUDED.stage,
  seller_organization_attio_id = EXCLUDED.seller_organization_attio_id,
  raw_attio = EXCLUDED.raw_attio,
  updated_at = now();
'@

Set-Content -Path $sqlPath -Value $sql -Encoding utf8

Write-Host "Prepared $($rows.Count) deals."
Write-Host "Wrote $csvPath"
Write-Host "Wrote $sqlPath"

if (-not $Apply) {
  Write-Host "DRY RUN: add -Apply to load deals into PostgreSQL."
  exit 0
}

$dockerDatabaseUrl = $DatabaseUrl.Replace("localhost:15432", "host.docker.internal:15432")
$mountPath = $OutputDir.Replace("\", "/")

docker run --rm `
  -e DATABASE_URL="$dockerDatabaseUrl" `
  -v "${mountPath}:/sync:ro" `
  postgres:16 `
  psql "$dockerDatabaseUrl" -v ON_ERROR_STOP=1 -f "/sync/sync-deals.sql"

Write-Host "PostgreSQL deals sync complete."
