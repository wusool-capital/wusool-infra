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

function Get-EntryParentRecordId {
  param([object]$Entry)

  if ($Entry.parent_record_id.record_id) { return $Entry.parent_record_id.record_id }
  if ($Entry.parent_record_id) { return $Entry.parent_record_id }
  if ($Entry.id.record_id) { return $Entry.id.record_id }
  if ($Entry.record_id) { return $Entry.record_id }
  return $null
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

function Get-ListRows {
  param(
    [string]$List,
    [hashtable]$CompanyLegacyByDevId
  )

  $rows = @()
  $seen = @{}
  $offset = 0

  while ($true) {
    Write-Host "Reading DEV list $List offset=$offset"
    $result = Invoke-AttioPost -Path "/lists/$List/entries/query" -Body @{ limit = $Limit; offset = $offset }
    $entries = @($result.data)

    foreach ($entry in $entries) {
      $devCompanyId = Get-EntryParentRecordId -Entry $entry
      if ([string]::IsNullOrWhiteSpace($devCompanyId) -or -not $CompanyLegacyByDevId.ContainsKey($devCompanyId)) {
        continue
      }

      $legacyId = $CompanyLegacyByDevId[$devCompanyId]
      if ($seen.ContainsKey($legacyId)) {
        continue
      }

      $seen[$legacyId] = $true
      $rows += [pscustomobject]@{
        org_attio_id    = $legacyId
        list_entry_id   = if ($entry.id.entry_id) { $entry.id.entry_id } else { $null }
        raw_attio_json  = ConvertTo-JsonText -Value $entry
      }
    }

    if ($entries.Count -lt $Limit) { break }
    $offset += $Limit
  }

  return $rows
}

New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

$companyLegacyByDevId = Get-CompanyLegacyByDevIdMap

$buyerRows = @(Get-ListRows -List "buyer_brain" -CompanyLegacyByDevId $companyLegacyByDevId)
$sellerRows = @(Get-ListRows -List "valuation_tool_leads" -CompanyLegacyByDevId $companyLegacyByDevId)
$mandateRows = @(Get-ListRows -List "buy_side_mandates" -CompanyLegacyByDevId $companyLegacyByDevId)

$buyerCsv = Join-Path $OutputDir "buyer_roles.csv"
$sellerCsv = Join-Path $OutputDir "seller_roles.csv"
$mandateCsv = Join-Path $OutputDir "mandates.csv"
$sqlPath = Join-Path $OutputDir "sync-list-roles.sql"

$buyerRows | Export-Csv -Path $buyerCsv -NoTypeInformation -Encoding utf8
$sellerRows | Export-Csv -Path $sellerCsv -NoTypeInformation -Encoding utf8
$mandateRows | Export-Csv -Path $mandateCsv -NoTypeInformation -Encoding utf8

$sql = @'
CREATE TEMP TABLE stg_buyer_roles (
  org_attio_id text,
  list_entry_id text,
  raw_attio_json text
);

CREATE TEMP TABLE stg_seller_roles (
  org_attio_id text,
  list_entry_id text,
  raw_attio_json text
);

CREATE TEMP TABLE stg_mandates (
  org_attio_id text,
  list_entry_id text,
  raw_attio_json text
);

\copy stg_buyer_roles FROM '/sync/buyer_roles.csv' WITH (FORMAT csv, HEADER true, NULL '');
\copy stg_seller_roles FROM '/sync/seller_roles.csv' WITH (FORMAT csv, HEADER true, NULL '');
\copy stg_mandates FROM '/sync/mandates.csv' WITH (FORMAT csv, HEADER true, NULL '');

INSERT INTO buyer_roles (
  org_attio_id,
  raw_attio,
  updated_at
)
SELECT
  org_attio_id,
  COALESCE(NULLIF(raw_attio_json, '')::jsonb, '{}'::jsonb),
  now()
FROM stg_buyer_roles
ON CONFLICT (org_attio_id) DO UPDATE SET
  raw_attio = EXCLUDED.raw_attio,
  updated_at = now();

INSERT INTO seller_roles (
  org_attio_id,
  raw_attio,
  updated_at
)
SELECT
  org_attio_id,
  COALESCE(NULLIF(raw_attio_json, '')::jsonb, '{}'::jsonb),
  now()
FROM stg_seller_roles
ON CONFLICT (org_attio_id) DO UPDATE SET
  raw_attio = EXCLUDED.raw_attio,
  updated_at = now();

INSERT INTO mandates (
  attio_id,
  side,
  buyer_attio_id,
  raw_attio,
  updated_at
)
SELECT
  list_entry_id,
  'buy',
  org_attio_id,
  COALESCE(NULLIF(raw_attio_json, '')::jsonb, '{}'::jsonb),
  now()
FROM stg_mandates
ON CONFLICT (attio_id) DO UPDATE SET
  side = EXCLUDED.side,
  buyer_attio_id = EXCLUDED.buyer_attio_id,
  raw_attio = EXCLUDED.raw_attio,
  updated_at = now();
'@

Set-Content -Path $sqlPath -Value $sql -Encoding utf8

Write-Host "Prepared buyer_roles: $($buyerRows.Count)"
Write-Host "Prepared seller_roles: $($sellerRows.Count)"
Write-Host "Prepared mandates: $($mandateRows.Count)"
Write-Host "Wrote $sqlPath"

if (-not $Apply) {
  Write-Host "DRY RUN: add -Apply to load list roles into PostgreSQL."
  exit 0
}

$dockerDatabaseUrl = $DatabaseUrl.Replace("localhost:15432", "host.docker.internal:15432")
$mountPath = $OutputDir.Replace("\", "/")

docker run --rm `
  -e DATABASE_URL="$dockerDatabaseUrl" `
  -v "${mountPath}:/sync:ro" `
  postgres:16 `
  psql "$dockerDatabaseUrl" -v ON_ERROR_STOP=1 -f "/sync/sync-list-roles.sql"

Write-Host "PostgreSQL list role sync complete."
