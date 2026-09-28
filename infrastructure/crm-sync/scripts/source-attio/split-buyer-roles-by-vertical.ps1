param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [ValidateRange(0, 1000000)]
  [int]$Limit = 0,
  [switch]$IsTest,
  [string]$Confirmation,
  [switch]$Apply
)

# Fans each buyer_role entry out into one entry per vertical: the parent org's
# `sector_focus` titles become `buyer_role.target_vertical`, one entry each.
#
# The existing entry is PATCHed into the org's first sector and never deleted.
# That preserves its Attio entry id, which is what `buyer_roles.legacy_entry_id`
# upserts on, which is what keeps `buyer_roles.id` stable -- and `match_results`
# (NOT NULL), `notes` and `tool_runs` all point at that id. Sectors 2..N are new
# entries with fresh ids that nothing references yet.
#
# Organizations are seeded oldest-parent-first. Reconciliation breaks ties on
# `created_at`, every entry created here is stamped today, and an org's newest
# entry is the live one -- so its children must be written last to win their
# verticals. Written newest-first, a superseded duplicate's copy would win and
# the stale mandate would go live.
#
# An org with no `sector_focus` is left alone: its entry keeps a NULL vertical
# rather than being assigned one we cannot evidence.
#
# Pause the webhook first (`sync-all-within-source.ps1`'s own pause/resume, or
# by hand). Not fatal if you forget -- the reconciler is vertical-aware as of
# PR #221 -- but each write fires an event that re-reconciles the whole org.
#
# Re-runnable: children carry `legacy_entry_id = "<parent's>:<vertical>"`, so a
# second run finds and patches them instead of duplicating the fan-out.

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($SourceApiKey)) {
  $SourceApiKey = [Environment]::GetEnvironmentVariable("SOURCE_ATTIO_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($SourceApiKey)) { throw "Missing SOURCE_ATTIO_API_KEY." }

$boundedToken = "APPLY_VERTICAL_SPLIT_TO_SOURCE"
$fullToken = "APPLY_ALL_VERTICAL_SPLIT_TO_SOURCE"
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
  # 8 attempts, same policy as sync-all-within-source.ps1: Attio 429s a bulk
  # run like this one routinely, and a half-applied fan-out is the worst state.
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

function Get-Value {
  param([object]$Values, [string]$Slug)
  $item = @($Values.$Slug) | Where-Object { $null -eq $_.active_until } | Select-Object -First 1
  if ($null -eq $item) { return $null }
  if ($item.option.title) { return [string]$item.option.title }
  if ($item.status.title) { return [string]$item.status.title }
  if ($null -ne $item.currency_value) { return $item.currency_value }
  if ($null -ne $item.target_record_id) { return [string]$item.target_record_id }
  if ($null -ne $item.value) { return $item.value }
  return $null
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

# SOURCE keeps ticket size as free text, and a few organizations wrote a bare
# number where the others wrote a range -- 5000000 rather than $5M. Same unit,
# unreadable beside the rest. A value that is only digits is read as USD and
# rendered in millions; anything already carrying a currency symbol is copied
# through untouched, because canonicalising "$20M-$100M" versus "$20-$100M" is
# a separate cleanup with its own judgement calls, and check_size_min/max stay
# authoritative for matching either way.
function Format-TicketSize {
  param([string]$Value)
  if ([string]::IsNullOrWhiteSpace($Value)) { return $Value }
  $trimmed = $Value.Trim()
  if ($trimmed -notmatch '^\d+$') { return $trimmed }
  $amount = [decimal]$trimmed
  if ($amount -ge 1000000) {
    $scaled = $amount / 1000000
    $suffix = "M"
  } elseif ($amount -ge 1000) {
    $scaled = $amount / 1000
    $suffix = "K"
  } else {
    return "`$$trimmed"
  }
  $text = if ($scaled -eq [Math]::Floor($scaled)) { [string][int]$scaled } else { $scaled.ToString("0.#") }
  return "`$$text$suffix"
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
  $raw = Get-Value -Values $Values -Slug "is_test"
  $entryIsTest = if ($null -eq $raw) { $false } else { [bool]$raw }
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

# Copied verbatim onto every child. Grouped by write shape, since Attio takes a
# different payload per attribute type. `target_vertical` is set per child and
# `legacy_entry_id` is namespaced, so neither is copied.
$enumSingleFields = @("model", "mandate_status", "deal_structure_tolerance", "relationship_warmth")
$enumMultiFields = @("target_region", "target_country")
$moneyFields = @(
  "ebitda_floor", "check_size_min", "check_size_max", "ev_ceiling",
  "ebitda_ceiling", "estimated_aum"
)
$booleanFields = @("earnout_tolerance", "profitable_only", "is_active", "is_test")
$integerFields = @("deals_introduced", "deals_converted")
$textFields = @(
  "investment_strategy", "notes", "acquisition_enrichment", "notable_investments",
  "key_personnel", "prior_gcc_acquisition"
)
$dateFields = @("last_mandate_briefing_date")

$optionMaps = @{}
foreach ($field in @("target_vertical") + $enumSingleFields + $enumMultiFields) {
  $response = Invoke-AttioRequest -Method Get -Path "/lists/buyer_role/attributes/$field/options"
  $map = @{}
  foreach ($option in @($response.data | Where-Object { -not $_.is_archived })) {
    $map[[string]$option.title] = [string]$option.id.option_id
  }
  $optionMaps[$field] = $map
}

function Resolve-Option {
  param([string]$Field, [string]$Title)
  if (-not $optionMaps[$Field].ContainsKey($Title)) {
    throw "buyer_role/$Field has no option '$Title'. Run ensure-schema.ps1 -Apply first."
  }
  return $optionMaps[$Field][$Title]
}

Write-Host "Reading buyer_role entries and organizations..."
$allEntries = Get-PagedData -Path "/lists/buyer_role/entries/query"
$organizations = Get-PagedData -Path "/objects/organizations/records/query"

Write-Json -Path (Join-Path $outputRoot "buyer-role-backup-$runId.json") -Value @{
  captured_at_utc = [DateTime]::UtcNow.ToString("o")
  list = "buyer_role"
  entry_count = $allEntries.Count
  entries = $allEntries
}

$orgById = @{}
foreach ($record in $organizations) {
  $orgById[[string]$record.id.record_id] = $record
}

$entries = @($allEntries | Where-Object { Test-InScope -Values $_.entry_values })

# Every entry already carrying a vertical, so a re-run patches its own children
# rather than fanning the same parent out twice.
$existingByLegacyId = @{}
foreach ($entry in $entries) {
  $legacyId = Get-Value -Values $entry.entry_values -Slug "legacy_entry_id"
  if (-not [string]::IsNullOrWhiteSpace([string]$legacyId)) {
    $existingByLegacyId[[string]$legacyId] = [string]$entry.id.entry_id
  }
}

$plans = [Collections.Generic.List[object]]::new()
$skipped = [ordered]@{ no_organization = 0; no_sector_focus = 0 }

$byOrg = $entries | Group-Object { Get-ParentRecordId -Entry $_ }
# Oldest parent first, so the live entry's children are written last.
$orgOrder = @(
  $byOrg | Sort-Object {
    ($_.Group | ForEach-Object { [string]$_.created_at } | Sort-Object | Select-Object -First 1)
  }
)
if ($Limit -gt 0) { $orgOrder = @($orgOrder | Select-Object -First $Limit) }

foreach ($group in $orgOrder) {
  $orgId = [string]$group.Name
  $org = $orgById[$orgId]
  if ($null -eq $org) { $skipped.no_organization += @($group.Group).Count; continue }

  # @() because PowerShell unwraps a one-element array on return, and a
  # bare string indexes to characters.
  $sectors = @(Get-Titles -Values $org.values -Slug "sector_focus")
  if ($sectors.Count -eq 0) { $skipped.no_sector_focus += @($group.Group).Count; continue }

  # geographic_focus was dropped from buyer_role 2026-09-26 -- the org value
  # now lands in target_region/target_country via normalize-buyer-geography.ps1,
  # which runs before this script.
  $carryOver = @{
    target_stage = (Get-Titles -Values $org.values -Slug "stage_focus") -join ", "
    ticket_size = Format-TicketSize ([string](Get-Value -Values $org.values -Slug "ticket_size"))
  }

  foreach ($entry in @($group.Group | Sort-Object { [string]$_.created_at })) {
    $values = $entry.entry_values
    $entryId = [string]$entry.id.entry_id
    $parentLegacyId = [string](Get-Value -Values $values -Slug "legacy_entry_id")
    $keyRoot = if ([string]::IsNullOrWhiteSpace($parentLegacyId)) { "entry:$entryId" } else { $parentLegacyId }
    # Every child inherits this verbatim, so a superseded duplicate stays
    # superseded in each of its verticals rather than being revived.
    $parentActive = Get-Value -Values $values -Slug "is_active"

    for ($i = 0; $i -lt $sectors.Count; $i++) {
      $vertical = [string]$sectors[$i]
      $payload = @{ target_vertical = (Resolve-Option -Field "target_vertical" -Title $vertical) }
      foreach ($field in $carryOver.Keys) {
        if (-not [string]::IsNullOrWhiteSpace($carryOver[$field])) {
          $payload[$field] = $carryOver[$field]
        }
      }

      if ($i -eq 0) {
        # The original entry: patched, never recreated, so its id survives.
        $plans.Add([ordered]@{
          action = "patch"
          entry_id = $entryId
          org_attio_id = $orgId
          vertical = $vertical
          legacy_entry_id = $keyRoot
          is_active = $parentActive
          values = $payload
        })
        continue
      }

      foreach ($field in $textFields) {
        $value = Get-Value -Values $values -Slug $field
        if (-not [string]::IsNullOrWhiteSpace([string]$value)) { $payload[$field] = [string]$value }
      }
      foreach ($field in $booleanFields + $integerFields + $dateFields + $moneyFields) {
        $value = Get-Value -Values $values -Slug $field
        if ($null -ne $value) { $payload[$field] = $value }
      }
      foreach ($field in $enumSingleFields) {
        $title = Get-Value -Values $values -Slug $field
        if (-not [string]::IsNullOrWhiteSpace([string]$title)) {
          $payload[$field] = Resolve-Option -Field $field -Title ([string]$title)
        }
      }
      foreach ($field in $enumMultiFields) {
        $titles = @(Get-Titles -Values $values -Slug $field)
        if ($titles.Count -gt 0) {
          $payload[$field] = @($titles | ForEach-Object { Resolve-Option -Field $field -Title $_ })
        }
      }
      $keyContact = Get-Value -Values $values -Slug "key_contact"
      if (-not [string]::IsNullOrWhiteSpace([string]$keyContact)) {
        $payload["key_contact"] = @{ target_object = "person"; target_record_id = [string]$keyContact }
      }

      $childKey = "$($keyRoot):$vertical"
      $payload["legacy_entry_id"] = $childKey
      $plans.Add([ordered]@{
        action = if ($existingByLegacyId.ContainsKey($childKey)) { "patch" } else { "create" }
        entry_id = if ($existingByLegacyId.ContainsKey($childKey)) { $existingByLegacyId[$childKey] } else { $null }
        org_attio_id = $orgId
        vertical = $vertical
        legacy_entry_id = $childKey
        parent_entry_id = $entryId
        is_active = $parentActive
        values = $payload
      })
    }
  }
}

$applyStats = [ordered]@{ patched = 0; created = 0; errors = 0 }
if ($Apply) {
  foreach ($plan in $plans) {
    try {
      if ($plan.action -eq "patch") {
        Invoke-AttioRequest -Method Patch -Path "/lists/buyer_role/entries/$($plan.entry_id)" `
          -Body @{ data = @{ entry_values = $plan.values } } | Out-Null
        $applyStats.patched++
      } else {
        $created = Invoke-AttioRequest -Method Post -Path "/lists/buyer_role/entries" -Body @{
          data = @{
            parent_record_id = $plan.org_attio_id
            parent_object = "organizations"
            entry_values = $plan.values
          }
        }
        $existingByLegacyId[$plan.legacy_entry_id] = [string]$created.data.id.entry_id
        $applyStats.created++
      }
    } catch {
      $applyStats.errors++
      throw
    }
  }
} else {
  foreach ($plan in $plans) {
    Write-Host "DRY RUN: would $($plan.action) $($plan.org_attio_id) -> $($plan.vertical)"
  }
}

$summary = [ordered]@{
  generated_at_utc = [DateTime]::UtcNow.ToString("o")
  run_id = $runId
  mode = if ($Apply) { if ($Limit -eq 0) { "apply" } else { "bounded-apply" } } else { "dry-run" }
  scope = if ($IsTest) { "test" } else { "production" }
  entries_in_list = $allEntries.Count
  entries_in_scope = $entries.Count
  organizations_planned = $orgOrder.Count
  planned_patches = @($plans | Where-Object { $_.action -eq "patch" }).Count
  planned_creates = @($plans | Where-Object { $_.action -eq "create" }).Count
  entries_after_split = $plans.Count + $skipped.no_sector_focus + $skipped.no_organization
  # 2 duplicate entries x 5 sectors must read 5 active / 5 inactive, never 1/9.
  active_after_split = @($plans | Where-Object { $_.is_active -eq $true }).Count
  inactive_after_split = @($plans | Where-Object { $_.is_active -ne $true }).Count
  skipped = $skipped
  apply = $applyStats
}

Write-Json -Path (Join-Path $outputRoot "buyer-role-split-plan.json") -Value @{
  summary = $summary
  sample = @($plans | Select-Object -First 10)
  plans = $plans
}

$summary | Format-List
Write-Host "Backup:  $outputRoot\buyer-role-backup-$runId.json"
Write-Host "Plan:    $outputRoot\buyer-role-split-plan.json"
