param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [ValidateRange(0, 1000000)]
  [int]$Limit = 0,
  [switch]$IsTest,
  [string]$Confirmation,
  [switch]$Apply
)

# Fills `seller_role.sector` from the parent organization's `sector_focus`.
#
# Only for orgs whose `type` includes "Target". On a Target record
# `sector_focus` names the industry the company *is* in, which is what a
# seller's sector means. On an investor-type record the same column names the
# industries they are hunting -- copying that onto a seller role would claim
# the company operates in sixteen sectors it has never traded in.
#
# Multi-valued, so no fan-out: one seller_role entry keeps one entry and gains
# every title its org carries. Unlike buyer_role, seller_role is not re-grained.
#
# Re-runnable: a patch is idempotent and an entry that already matches its org
# is skipped, so this can ride along with every sync.
#
# `matching_engine/persistence/mappers.py` still reads the seller's sector from
# `organizations.sector_focus`. Repoint it to `seller_roles.sector` only once
# this has run and been verified -- that is the gate on retiring the org column.

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($SourceApiKey)) {
  $SourceApiKey = [Environment]::GetEnvironmentVariable("SOURCE_ATTIO_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($SourceApiKey)) { throw "Missing SOURCE_ATTIO_API_KEY." }

$boundedToken = "APPLY_SELLER_SECTOR_TO_SOURCE"
$fullToken = "APPLY_ALL_SELLER_SECTOR_TO_SOURCE"
if ($Apply) {
  $isBoundedApply = $Limit -ge 1 -and $Limit -le 10 -and $Confirmation -eq $boundedToken
  $isFullApply = $Limit -eq 0 -and $Confirmation -eq $fullToken
  if (-not $isBoundedApply -and -not $isFullApply) {
    throw "Use a 1-10 -Limit with $boundedToken, or -Limit 0 with $fullToken."
  }
}

$headers = @{
  Authorization = "Bearer $($SourceApiKey.Trim())"
  Accept = "application/json"
  "Content-Type" = "application/json"
}

$outputRoot = Join-Path $PSScriptRoot "..\..\..\..\outputs\attio_migration"
$null = New-Item -ItemType Directory -Force -Path $outputRoot

function Invoke-AttioRequest {
  param(
    [ValidateSet("Get", "Post", "Patch")][string]$Method,
    [string]$Path,
    [object]$Body
  )
  $parameters = @{ Method = $Method; Uri = "https://api.attio.com/v2$Path"; Headers = $headers }
  if ($null -ne $Body) {
    $parameters.Body = [Text.Encoding]::UTF8.GetBytes(($Body | ConvertTo-Json -Depth 30))
  }
  for ($attempt = 1; ; $attempt++) {
    try { return Invoke-RestMethod @parameters }
    catch {
      $status = [int]$_.Exception.Response.StatusCode
      if ($attempt -ge 8 -or ($status -ne 429 -and $status -lt 500)) { throw }
      Start-Sleep -Seconds ([Math]::Min(5 * $attempt, 60))
    }
  }
}

function Get-PagedData {
  param([string]$Path)
  $all = @()
  for ($offset = 0; ; $offset += 500) {
    $response = Invoke-AttioRequest -Method Post -Path $Path -Body @{ limit = 500; offset = $offset }
    $page = @($response.data)
    $all += $page
    if ($page.Count -lt 500) { return $all }
  }
}

function Get-Titles {
  param([object]$Values, [string]$Slug)
  return @(
    $Values.$Slug |
      Where-Object { $null -eq $_.active_until } |
      ForEach-Object { if ($_.option.title) { [string]$_.option.title } else { [string]$_.value } } |
      Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
  )
}

# Attio's own `is_test` filter treats an unset checkbox as false, so scope is
# decided here on the raw value instead of in the query.
function Test-InScope {
  param([object]$Values)
  $item = @($Values.is_test) | Where-Object { $null -eq $_.active_until } | Select-Object -First 1
  $entryIsTest = if ($null -eq $item) { $false } else { [bool]$item.value }
  return $entryIsTest -eq [bool]$IsTest
}

$decisions = Get-Content (Join-Path $PSScriptRoot "config\migration-decisions.json") -Raw |
  ConvertFrom-Json
$expectedWorkspaceId = [string]$decisions.workspace_id
$organizationsObject = Invoke-AttioRequest -Method Get -Path "/objects/organizations"
$connectedWorkspaceId = [string]$organizationsObject.data.id.workspace_id
if ($connectedWorkspaceId -ne $expectedWorkspaceId) {
  throw "Workspace mismatch. Expected $expectedWorkspaceId but connected to $connectedWorkspaceId."
}

$optionMap = @{}
$response = Invoke-AttioRequest -Method Get -Path "/lists/seller_role/attributes/sector/options"
foreach ($option in @($response.data | Where-Object { -not $_.is_archived })) {
  $optionMap[[string]$option.title] = [string]$option.id.option_id
}

Write-Host "Reading seller_role entries and organizations..."
$allEntries = Get-PagedData -Path "/lists/seller_role/entries/query"
$organizations = Get-PagedData -Path "/objects/organizations/records/query"

$orgById = @{}
foreach ($record in $organizations) { $orgById[[string]$record.id.record_id] = $record }

$plans = [Collections.Generic.List[object]]::new()
$skipped = [ordered]@{ no_organization = 0; not_target_type = 0; no_sector_focus = 0; already_set = 0 }

foreach ($entry in @($allEntries | Where-Object { Test-InScope -Values $_.entry_values })) {
  $orgId = [string]$entry.parent_record_id.record_id
  $org = $orgById[$orgId]
  if ($null -eq $org) { $skipped.no_organization++; continue }

  if ((Get-Titles -Values $org.values -Slug "type") -notcontains "Target") {
    $skipped.not_target_type++
    continue
  }

  $sectors = Get-Titles -Values $org.values -Slug "sector_focus"
  if ($sectors.Count -eq 0) { $skipped.no_sector_focus++; continue }

  $current = Get-Titles -Values $entry.entry_values -Slug "sector"
  if (@(Compare-Object $current $sectors).Count -eq 0) { $skipped.already_set++; continue }

  foreach ($title in $sectors) {
    if (-not $optionMap.ContainsKey($title)) {
      throw "seller_role/sector has no option '$title'. Run ensure-schema.ps1 -Apply first."
    }
  }

  $plans.Add([ordered]@{
    entry_id = [string]$entry.id.entry_id
    org_attio_id = $orgId
    sectors = $sectors
    values = @{ sector = @($sectors | ForEach-Object { $optionMap[$_] }) }
  })
}

if ($Limit -gt 0 -and $plans.Count -gt $Limit) {
  $plans = [Collections.Generic.List[object]](@($plans | Select-Object -First $Limit))
}

$applyStats = [ordered]@{ patched = 0; errors = 0 }
if ($Apply) {
  foreach ($plan in $plans) {
    try {
      Invoke-AttioRequest -Method Patch -Path "/lists/seller_role/entries/$($plan.entry_id)" `
        -Body @{ data = @{ entry_values = $plan.values } } | Out-Null
      $applyStats.patched++
    } catch {
      $applyStats.errors++
      throw
    }
  }
} else {
  foreach ($plan in $plans) {
    Write-Host "DRY RUN: would set $($plan.org_attio_id) sector = $($plan.sectors -join ', ')"
  }
}

$summary = [ordered]@{
  generated_at_utc = [DateTime]::UtcNow.ToString("o")
  mode = if ($Apply) { if ($Limit -eq 0) { "apply" } else { "bounded-apply" } } else { "dry-run" }
  scope = if ($IsTest) { "test" } else { "production" }
  entries_in_list = $allEntries.Count
  planned_patches = $plans.Count
  skipped = $skipped
  apply = $applyStats
}

[IO.File]::WriteAllText(
  (Join-Path $outputRoot "seller-sector-plan.json"),
  (@{ summary = $summary; sample = @($plans | Select-Object -First 10); plans = $plans } |
    ConvertTo-Json -Depth 40),
  [Text.UTF8Encoding]::new($false)
)

$summary | Format-List
Write-Host "Plan: $outputRoot\seller-sector-plan.json"
