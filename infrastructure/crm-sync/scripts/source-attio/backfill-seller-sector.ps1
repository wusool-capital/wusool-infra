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
# Only when the org lists exactly one sector. That column means two different
# things: on a seller it names the industry the company *is* in, on an investor
# it names the industries it is hunting. The count separates them -- every
# seller in the live data carries one value, every investor carries several --
# and it separates them better than `type`, which half the seller orgs leave
# blank. A company that is both buyer and seller lists many, so it is skipped.
#
# `sector` is multi-valued but only ever gets the one title, so no fan-out:
# unlike buyer_role, seller_role is not re-grained.
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

# The entries API returns `parent_record_id` as a bare string; the object form
# only shows up in some responses. Same shape check `_internal/lists.ps1` makes.
function Get-ParentRecordId {
  param([object]$Entry)
  if ($Entry.parent_record_id.record_id) { return [string]$Entry.parent_record_id.record_id }
  if ($Entry.parent_record_id) { return [string]$Entry.parent_record_id }
  return $null
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
$skipped = [ordered]@{
  no_organization = 0; no_sector_focus = 0; multi_sector_org = 0; already_set = 0
}

foreach ($entry in @($allEntries | Where-Object { Test-InScope -Values $_.entry_values })) {
  $orgId = Get-ParentRecordId -Entry $entry
  $org = $orgById[$orgId]
  if ($null -eq $org) { $skipped.no_organization++; continue }

  # @() because PowerShell unwraps a one-element array on return.
  $sectors = @(Get-Titles -Values $org.values -Slug "sector_focus")
  if ($sectors.Count -eq 0) { $skipped.no_sector_focus++; continue }
  if ($sectors.Count -gt 1) { $skipped.multi_sector_org++; continue }

  $current = @(Get-Titles -Values $entry.entry_values -Slug "sector")
  if ($current.Count -eq $sectors.Count -and
      @(Compare-Object $current $sectors).Count -eq 0) { $skipped.already_set++; continue }

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
