param(
  [string]$DatabaseUrl = $env:DATABASE_URL
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) {
  throw "Set DATABASE_URL or pass -DatabaseUrl."
}

if (-not (Get-Command psql -ErrorAction SilentlyContinue)) {
  throw "psql was not found on PATH. Install PostgreSQL client tools before validating."
}

$requiredTables = @(
  "users",
  "organizations",
  "people",
  "deals",
  "mandates",
  "buyer_roles",
  "seller_roles",
  "activities",
  "signals",
  "buyer_intel",
  "seller_financials",
  "mandate_targets",
  "match_scores",
  "documents",
  "vertical_kb",
  "graph_edges",
  "deal_stage_events",
  "attio_sync_state",
  "attio_raw_events"
)

$tableList = $requiredTables -join "','"
$query = "select table_name from information_schema.tables where table_schema = 'public' and table_name in ('$tableList') order by table_name;"
$found = psql $DatabaseUrl -At -c $query
$foundSet = @{}
$found | ForEach-Object { if ($_ -ne "") { $foundSet[$_] = $true } }

$missing = $requiredTables | Where-Object { -not $foundSet.ContainsKey($_) }
if ($missing.Count -gt 0) {
  throw "Missing required tables: $($missing -join ', ')"
}

Write-Host "Schema validation passed. Required tables exist."
