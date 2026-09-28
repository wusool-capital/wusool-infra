param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [ValidateRange(0, 1000000)]
  [int]$Limit = 0,
  [string]$Confirmation,
  [switch]$Apply
)

# Repairs `buyer_role.is_active` after the 2026-09-28 nightly flattened it.
#
# WHAT HAPPENED. The GitHub Actions billing block cleared, so the nightly full
# resync ran green at 00:15 UTC on 2026-09-28 -- against prod, which was still
# at PR #219 and reconciled `is_active` once per ORGANIZATION. It switched off
# every vertical but one: 913 active entries became 274. Nothing was deleted
# and no other field moved; only the checkbox flipped, on 639 entries.
#
# Prod was deployed to #229 at 13:34 UTC the same day, so the live reconciler
# now groups per (org, vertical) and repairs Attio itself. This script does
# that repair now, on its own, instead of waiting for a full resync -- so the
# flag can be fixed and verified without also rewriting every Postgres row in
# the same step.
#
# THE RULE, COPIED FROM THE DEPLOYED RECONCILER so that the two agree and the
# next resync is a no-op on this field
# (ddl_commands/persistence/attio_sync.py:617-661, vertical_key at :608):
#
#   1. group every buyer_role entry by its parent organization
#   2. sort each org's entries by created_at, NEWEST FIRST
#   3. walk them in that order; an entry is active if no earlier entry in the
#      group has already claimed its `target_vertical`
#   4. an entry with no target_vertical has key `null` -- all such entries in
#      one org share a single group, so exactly one stays active
#
# Deliberately NOT filtered by `is_test`: the reconciler groups the raw
# page-through (attio_sync_full_resync.py:522), so the three test entries take
# part in reconciliation too. Filtering them here would compute a different
# answer than the resync and the two would fight every night.
#
# WRITES ONE FIELD. `buyer_role.is_active`, and only on entries whose current
# value disagrees with the rule. No other attribute, no other list or object,
# and never Postgres -- the mirror follows on the next resync.
#
# Re-runnable: a second run plans zero patches.

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($SourceApiKey)) {
  $SourceApiKey = [Environment]::GetEnvironmentVariable("SOURCE_ATTIO_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($SourceApiKey)) { throw "Missing SOURCE_ATTIO_API_KEY." }

$boundedToken = "APPLY_IS_ACTIVE_REPAIR_TO_SOURCE"
$fullToken = "APPLY_ALL_IS_ACTIVE_REPAIR_TO_SOURCE"
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

$runId = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
$outputRoot = Join-Path $PSScriptRoot "..\..\..\..\outputs\attio_migration"
$null = New-Item -ItemType Directory -Force -Path $outputRoot

function Write-Json {
  param([string]$Path, [object]$Value)
  [IO.File]::WriteAllText(
    $Path, ($Value | ConvertTo-Json -Depth 40), [Text.UTF8Encoding]::new($false)
  )
}

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

function Get-ActiveItems {
  param([object]$Values, [string]$Slug)
  return @($Values.$Slug | Where-Object { $null -eq $_.active_until })
}

function Get-OptionTitle {
  param([object]$Values, [string]$Slug)
  $item = @(Get-ActiveItems -Values $Values -Slug $Slug) | Select-Object -First 1
  if ($null -eq $item) { return $null }
  if ($item.option.title) { return [string]$item.option.title }
  $text = [string]$item.value
  if ([string]::IsNullOrWhiteSpace($text)) { return $null }
  return $text
}

function Get-Flag {
  param([object]$Values, [string]$Slug)
  $item = @(Get-ActiveItems -Values $Values -Slug $Slug) | Select-Object -First 1
  if ($null -eq $item) { return $false }
  return [bool]$item.value
}

function Get-ParentRecordId {
  param([object]$Entry)
  if ($Entry.parent_record_id.record_id) { return [string]$Entry.parent_record_id.record_id }
  if ($Entry.parent_record_id) { return [string]$Entry.parent_record_id }
  return $null
}

$decisions = Get-Content (Join-Path $PSScriptRoot "config\migration-decisions.json") -Raw |
  ConvertFrom-Json
$expectedWorkspaceId = [string]$decisions.workspace_id
$organizationsObject = Invoke-AttioRequest -Method Get -Path "/objects/organizations"
$connectedWorkspaceId = [string]$organizationsObject.data.id.workspace_id
if ($connectedWorkspaceId -ne $expectedWorkspaceId) {
  throw "Workspace mismatch. Expected $expectedWorkspaceId but connected to $connectedWorkspaceId."
}

Write-Host "Reading buyer_role entries..."
$allEntries = Get-PagedData -Path "/lists/buyer_role/entries/query"

Write-Json -Path (Join-Path $outputRoot "buyer-role-is-active-backup-$runId.json") -Value @{
  captured_at_utc = [DateTime]::UtcNow.ToString("o")
  list = "buyer_role"
  entry_count = $allEntries.Count
  entries = $allEntries
}

# Group by parent org, exactly as group_entries_by_org does.
$byOrg = @{}
foreach ($entry in $allEntries) {
  $orgId = Get-ParentRecordId -Entry $entry
  if (-not $byOrg.ContainsKey($orgId)) { $byOrg[$orgId] = [Collections.Generic.List[object]]::new() }
  $byOrg[$orgId].Add($entry)
}

$plans = [Collections.Generic.List[object]]::new()
$desiredActive = 0
$currentActive = 0
$missingCreatedAt = 0

foreach ($orgId in $byOrg.Keys) {
  # Newest created_at wins its vertical -- the same tiebreak the reconciler
  # and lists.ps1 both use. An entry with no created_at sorts last rather
  # than blowing up the comparison.
  $siblings = @($byOrg[$orgId] | Sort-Object -Property @{
    Expression = {
      if ([string]::IsNullOrWhiteSpace([string]$_.created_at)) { [DateTime]::MinValue }
      else { [DateTime]$_.created_at }
    }
  } -Descending)

  $claimed = [Collections.Generic.HashSet[string]]::new()
  foreach ($entry in $siblings) {
    if ([string]::IsNullOrWhiteSpace([string]$entry.created_at)) { $missingCreatedAt++ }

    $vertical = Get-OptionTitle -Values $entry.entry_values -Slug "target_vertical"
    # A null vertical is one shared group per org, not one group per entry --
    # matching vertical_key returning None.
    $key = if ($null -eq $vertical) { "`0<null>" } else { $vertical }
    $shouldBeActive = -not $claimed.Contains($key)
    [void]$claimed.Add($key)

    $isActive = Get-Flag -Values $entry.entry_values -Slug "is_active"
    if ($isActive) { $currentActive++ }
    if ($shouldBeActive) { $desiredActive++ }
    if ($isActive -eq $shouldBeActive) { continue }

    $plans.Add([ordered]@{
      entry_id = [string]$entry.id.entry_id
      org_attio_id = $orgId
      vertical = $vertical
      created_at = [string]$entry.created_at
      is_test = (Get-Flag -Values $entry.entry_values -Slug "is_test")
      from = $isActive
      to = $shouldBeActive
    })
  }
}

if ($Limit -gt 0 -and $plans.Count -gt $Limit) {
  $plans = [Collections.Generic.List[object]](@($plans | Select-Object -First $Limit))
}

$applyStats = [ordered]@{ patched = 0; errors = 0 }
if ($Apply) {
  foreach ($plan in $plans) {
    try {
      Invoke-AttioRequest -Method Patch -Path "/lists/buyer_role/entries/$($plan.entry_id)" `
        -Body @{ data = @{ entry_values = @{ is_active = $plan.to } } } | Out-Null
      $applyStats.patched++
    } catch {
      $applyStats.errors++
      throw
    }
  }
} else {
  foreach ($plan in @($plans | Select-Object -First 15)) {
    Write-Host ("DRY RUN: {0} [{1}] {2} -> {3}" -f `
      $plan.entry_id, $plan.vertical, $plan.from, $plan.to)
  }
  if ($plans.Count -gt 15) { Write-Host "... and $($plans.Count - 15) more" }
}

$summary = [ordered]@{
  generated_at_utc = [DateTime]::UtcNow.ToString("o")
  run_id = $runId
  mode = if ($Apply) { if ($Limit -eq 0) { "apply" } else { "bounded-apply" } } else { "dry-run" }
  entries_in_list = $allEntries.Count
  organizations = $byOrg.Keys.Count
  active_now = $currentActive
  active_after = $desiredActive
  planned_patches = $plans.Count
  turning_on = @($plans | Where-Object { $_.to }).Count
  turning_off = @($plans | Where-Object { -not $_.to }).Count
  touching_test_entries = @($plans | Where-Object { $_.is_test }).Count
  entries_without_created_at = $missingCreatedAt
  apply = $applyStats
}

Write-Json -Path (Join-Path $outputRoot "buyer-role-is-active-plan.json") -Value @{
  summary = $summary
  sample = @($plans | Select-Object -First 10)
  plans = $plans
}

$summary | Format-List
Write-Host "Backup: $outputRoot\buyer-role-is-active-backup-$runId.json"
Write-Host "Plan:   $outputRoot\buyer-role-is-active-plan.json"
