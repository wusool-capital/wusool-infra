param(
 [ValidateSet("buyer_role","seller_role")][string]$Task,
 [string]$SourceApiKey=$env:SOURCE_ATTIO_API_KEY,[string]$DevApiKey=$env:DEV_ATTIO_API_KEY,
 [int]$SampleSize=10,[int]$StartIndex=0,[int]$Limit=0,[string]$OutputSuffix,
 [string]$Confirmation,[switch]$Apply
)
$ErrorActionPreference="Stop"
function Invoke-BuyerRole {
param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [string]$DevApiKey = $env:DEV_ATTIO_API_KEY,
  [int]$SampleSize = 10,
  [ValidateRange(0, 1000000)]
  [int]$StartIndex = 0,
  [int]$Limit = 0,
  [string]$OutputSuffix,
  [string]$Confirmation,
  [switch]$Apply
)


$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($SourceApiKey)) {
  $SourceApiKey = [Environment]::GetEnvironmentVariable("SOURCE_ATTIO_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($DevApiKey)) {
  $DevApiKey = [Environment]::GetEnvironmentVariable("DEV_ATTIO_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($SourceApiKey)) { throw "Missing SOURCE_ATTIO_API_KEY." }
if ([string]::IsNullOrWhiteSpace($DevApiKey)) { throw "Missing DEV_ATTIO_API_KEY." }
if ($Apply) {
  $isBoundedApply = $Limit -ge 1 -and $Limit -le 10 -and
    $Confirmation -eq "APPLY_BUYER_ROLE_TO_DEV"
  $isFullApply = $Limit -eq 0 -and
    $Confirmation -eq "APPLY_ALL_BUYER_ROLE_TO_DEV"
  $isParallelChunk = $Limit -gt 0 -and $StartIndex -ge 0 -and
    $Confirmation -eq "APPLY_ALL_BUYER_ROLE_TO_DEV"
  if (-not $isBoundedApply -and -not $isFullApply -and -not $isParallelChunk) {
    throw "Use a 1-10 limit with APPLY_BUYER_ROLE_TO_DEV, or Limit 0 with APPLY_ALL_BUYER_ROLE_TO_DEV."
  }
}

$sourceHeaders = @{
  Authorization = "Bearer $($SourceApiKey.Trim())"
  Accept = "application/json"
  "Content-Type" = "application/json"
}
$devHeaders = @{
  Authorization = "Bearer $($DevApiKey.Trim())"
  Accept = "application/json"
  "Content-Type" = "application/json"
}

$migrationRoot = Split-Path $PSScriptRoot -Parent
$decisions = Get-Content (Join-Path $migrationRoot "config\migration-decisions.json") -Raw |
  ConvertFrom-Json
$expectedWorkspaceId = [string]$decisions.dev_workspace_id
# Blank-duplicate SOURCE companies (a second lead-magnet submission for a
# company that already exists) that were never migrated into DEV
# Organizations and so block parent resolution below. SOURCE is read-only
# to this tooling, so the duplicate can't be repointed at the source --
# instead it's aliased here to the real, already-migrated SOURCE company id.
$duplicateCompanyAlias = @{}
if ($decisions.duplicate_source_company_ids.mapping) {
  foreach ($property in $decisions.duplicate_source_company_ids.mapping.PSObject.Properties) {
    $duplicateCompanyAlias[[string]$property.Name] = [string]$property.Value
  }
}
$outputName = if ([string]::IsNullOrWhiteSpace($OutputSuffix)) {
  "buyer-role-plan.json"
} else {
  "buyer-role-plan-$OutputSuffix.json"
}
$outputPath = Join-Path $migrationRoot "..\..\..\outputs\attio_migration\$outputName"

function Invoke-AttioRequest {
  param(
    [ValidateSet("Get", "Post", "Patch")][string]$Method,
    [hashtable]$Headers,
    [string]$Path,
    [object]$Body
  )
  $parameters = @{
    Method = $Method
    Uri = "https://api.attio.com/v2$Path"
    Headers = $Headers
  }
  if ($null -ne $Body) {
    $parameters.Body = [System.Text.Encoding]::UTF8.GetBytes(
      ($Body | ConvertTo-Json -Depth 30)
    )
  }
  Invoke-RestMethod @parameters
}

function Get-ParentRecordId {
  param([object]$Entry)
  if ($Entry.parent_record_id.record_id) { return [string]$Entry.parent_record_id.record_id }
  if ($Entry.parent_record_id) { return [string]$Entry.parent_record_id }
  if ($Entry.id.record_id) { return [string]$Entry.id.record_id }
  return $null
}

function Get-RecordId {
  param([object]$Record)
  if ($Record.id.record_id) { return [string]$Record.id.record_id }
  return [string]$Record.record_id
}

function Get-Value {
  param([object]$Values, [string]$Slug)
  $item = @($Values.$Slug) |
    Where-Object { $null -eq $_.active_until } |
    Select-Object -First 1
  if ($null -eq $item) { return $null }
  if ($null -ne $item.value) { return $item.value }
  if ($item.option.title) { return [string]$item.option.title }
  if ($item.status.title) { return [string]$item.status.title }
  if ($null -ne $item.currency_value) { return $item.currency_value }
  return $null
}

function Get-DistinctValues {
  param([object[]]$Entries, [string]$Slug)
  return @(
    $Entries |
      ForEach-Object { Get-Value -Values $_.entry_values -Slug $Slug } |
      Where-Object {
        $null -ne $_ -and
        (-not ($_ -is [string]) -or -not [string]::IsNullOrWhiteSpace($_))
      } |
      ForEach-Object {
        if ($_ -is [string]) { $_.Trim() } else { $_ }
      } |
      Sort-Object -Unique
  )
}

function Add-UniqueScalar {
  param(
    [hashtable]$Target,
    [System.Collections.Generic.List[object]]$Conflicts,
    [object[]]$Entries,
    [string]$SourceSlug,
    [string]$TargetSlug,
    [ValidateSet("plain", "currency")][string]$Kind = "plain"
  )
  $values = @(Get-DistinctValues -Entries $Entries -Slug $SourceSlug)
  if ($values.Count -eq 0) { return }
  if ($values.Count -gt 1) {
    $Conflicts.Add([pscustomobject]@{
      target_field = $TargetSlug
      reason = "multiple_distinct_nonblank_values"
      value_count = $values.Count
    })
    return
  }
  if ($Kind -eq "currency") {
    $Target[$TargetSlug] = @{
      currency_value = [decimal]$values[0]
    }
  } else {
    $Target[$TargetSlug] = $values[0]
  }
}

function Add-MergedText {
  param(
    [hashtable]$Target,
    [object[]]$Entries,
    [string]$SourceSlug,
    [string]$TargetSlug
  )
  $values = @(Get-DistinctValues -Entries $Entries -Slug $SourceSlug)
  if ($values.Count -gt 0) {
    $Target[$TargetSlug] = $values -join "`r`n`r`n"
  }
}

function Add-EntryScalar {
  param(
    [hashtable]$Target,
    [object]$Entry,
    [string]$SourceSlug,
    [string]$TargetSlug,
    [ValidateSet("plain", "currency")][string]$Kind = "plain",
    # SOURCE's own *_aed fields are real AED figures; DEV's equivalent
    # currency attributes now default to USD (2026-08-25 cleanup) -- set this
    # so the migrated number is an actual USD-equivalent, not an AED number
    # under a USD label. Fixed peg (1 USD = 3.6725 AED), matching the rate
    # already used elsewhere in this file's check_size backfill.
    [switch]$AedToUsd
  )
  $raw = Get-Value -Values $Entry.entry_values -Slug $SourceSlug
  if ($null -eq $raw) { return }
  if ($raw -is [string]) {
    $raw = $raw.Trim()
    if ([string]::IsNullOrWhiteSpace($raw)) { return }
  }
  if ($Kind -eq "currency") {
    $amount = [decimal]$raw
    if ($AedToUsd) { $amount = [Math]::Round($amount / [decimal]3.6725, 2) }
    $Target[$TargetSlug] = @{ currency_value = $amount }
  } else {
    $Target[$TargetSlug] = $raw
  }
}

function Add-EntryText {
  param(
    [hashtable]$Target,
    [object]$Entry,
    [string]$SourceSlug,
    [string]$TargetSlug
  )
  $raw = Get-Value -Values $Entry.entry_values -Slug $SourceSlug
  if ($null -eq $raw) { return }
  $text = ([string]$raw).Trim()
  if ($text) { $Target[$TargetSlug] = $text }
}

function Get-EntryValueTitles {
  param([object]$Entry, [string]$Slug)
  return @(@($Entry.entry_values.$Slug) | Where-Object { $null -eq $_.active_until } | ForEach-Object { if ($_.option.title) { [string]$_.option.title } } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
}

function Normalize-PersonName {
  param([string]$Name)
  if ([string]::IsNullOrWhiteSpace($Name)) { return $null }
  return (($Name.Trim().ToLowerInvariant() -replace "[^\p{L}\p{Nd}]+", " ") -replace "\s+", " ").Trim()
}

function Get-PersonName {
  param([object]$Values)
  $item = @($Values.name) | Where-Object { $null -eq $_.active_until } | Select-Object -First 1
  if ($null -eq $item) { return $null }
  if ($item.full_name) { return [string]$item.full_name }
  if ($item.value) { return [string]$item.value }
  return $null
}

function Get-ReferenceIds {
  param([object]$Values, [string]$Slug)
  return @($Values.$Slug | Where-Object { $null -eq $_.active_until -and $_.target_record_id } | ForEach-Object { [string]$_.target_record_id })
}

$devOrganization = Invoke-AttioRequest -Method Get -Headers $devHeaders `
  -Path "/objects/organizations"
$connectedWorkspaceId = [string]$devOrganization.data.id.workspace_id
if ($connectedWorkspaceId -ne $expectedWorkspaceId) {
  throw "DEV workspace mismatch. Expected $expectedWorkspaceId but connected to $connectedWorkspaceId."
}

$devBuyerRole = Invoke-AttioRequest -Method Get -Headers $devHeaders `
  -Path "/lists/buyer_role"
if (@($devBuyerRole.data.parent_object) -notcontains "organizations") {
  throw "DEV buyer_role is not parented to organizations."
}

$sourceEntries = @()
for ($offset = 0; ; $offset += 500) {
  $response = Invoke-AttioRequest -Method Post -Headers $sourceHeaders `
    -Path "/lists/buyer_brain/entries/query" -Body @{ limit = 500; offset = $offset }
  $page = @($response.data)
  $sourceEntries += $page
  if ($page.Count -lt 500) { break }
}

$devOrganizationByLegacyId = @{}
for ($offset = 0; ; $offset += 500) {
  $response = Invoke-AttioRequest -Method Post -Headers $devHeaders `
    -Path "/objects/organizations/records/query" -Body @{ limit = 500; offset = $offset }
  $page = @($response.data)
  foreach ($record in $page) {
    $legacyId = Get-Value -Values $record.values -Slug "legacy_attio_id"
    if (-not [string]::IsNullOrWhiteSpace($legacyId)) {
      if ($devOrganizationByLegacyId.ContainsKey([string]$legacyId)) {
        throw "DEV Organization legacy_attio_id is not unique."
      }
      $devOrganizationByLegacyId[[string]$legacyId] = Get-RecordId -Record $record
    }
  }
  if ($page.Count -lt 500) { break }
}

$sourcePersonById = @{}
$sourcePersonIdsByName = @{}
for ($offset = 0; ; $offset += 500) {
  $response = Invoke-AttioRequest -Method Post -Headers $sourceHeaders `
    -Path "/objects/people/records/query" -Body @{ limit = 500; offset = $offset }
  $page = @($response.data)
  foreach ($record in $page) {
    $recordId = Get-RecordId -Record $record
    $name = Get-PersonName -Values $record.values
    $normalized = Normalize-PersonName -Name $name
    $sourcePersonById[$recordId] = [pscustomobject]@{ Id=$recordId; Name=$name; NormalizedName=$normalized }
    if ($normalized) {
      if (-not $sourcePersonIdsByName.ContainsKey($normalized)) { $sourcePersonIdsByName[$normalized] = [System.Collections.Generic.List[string]]::new() }
      $sourcePersonIdsByName[$normalized].Add($recordId)
    }
  }
  if ($page.Count -lt 500) { break }
}

$sourceCompanyTeam = @{}
for ($offset = 0; ; $offset += 500) {
  $response = Invoke-AttioRequest -Method Post -Headers $sourceHeaders `
    -Path "/objects/companies/records/query" -Body @{ limit = 500; offset = $offset }
  $page = @($response.data)
  foreach ($record in $page) { $sourceCompanyTeam[(Get-RecordId -Record $record)] = @(Get-ReferenceIds -Values $record.values -Slug "team") }
  if ($page.Count -lt 500) { break }
}

$devPersonByLegacyId = @{}
for ($offset = 0; ; $offset += 500) {
  $response = Invoke-AttioRequest -Method Post -Headers $devHeaders `
    -Path "/objects/person/records/query" -Body @{ limit = 500; offset = $offset }
  $page = @($response.data)
  foreach ($record in $page) {
    $legacyId = Get-Value -Values $record.values -Slug "legacy_attio_id"
    if ($legacyId) { $devPersonByLegacyId[[string]$legacyId] = Get-RecordId -Record $record }
  }
  if ($page.Count -lt 500) { break }
}

$plans = [System.Collections.Generic.List[object]]::new()
$unresolvedParents = [System.Collections.Generic.List[string]]::new()
$groups = $sourceEntries | Group-Object { Get-ParentRecordId -Entry $_ }

foreach ($group in $groups) {
  $sourceParentId = [string]$group.Name
  if ($duplicateCompanyAlias.ContainsKey($sourceParentId)) { $sourceParentId = $duplicateCompanyAlias[$sourceParentId] }
  if (-not $devOrganizationByLegacyId.ContainsKey($sourceParentId)) {
    $unresolvedParents.Add($sourceParentId)
    continue
  }
  $devParentId = $devOrganizationByLegacyId[$sourceParentId]

  # Every raw SOURCE entry becomes its own DEV entry -- duplicates are no
  # longer merged. Sorted newest-first so entries[0] is the one flagged
  # is_active = true; every other duplicate in the group is is_active = false.
  $entries = @(@($group.Group) | Sort-Object { [datetime]$_.created_at } -Descending)

  for ($i = 0; $i -lt $entries.Count; $i++) {
    $entry = $entries[$i]
    $sourceEntryId = if ($entry.id.entry_id) { [string]$entry.id.entry_id } else { [string]$entry.entry_id }
    $isActive = ($i -eq 0)

    $values = @{}
    Add-EntryScalar -Target $values -Entry $entry -SourceSlug "buyer_model" -TargetSlug "model"
    Add-EntryScalar -Target $values -Entry $entry -SourceSlug "mandate_status" -TargetSlug "mandate_status"
    Add-EntryScalar -Target $values -Entry $entry -SourceSlug "ebitda_floor_aed" -TargetSlug "ebitda_floor" -Kind currency -AedToUsd
    Add-EntryScalar -Target $values -Entry $entry -SourceSlug "check_size_min_aed" -TargetSlug "check_size_min" -Kind currency -AedToUsd
    Add-EntryScalar -Target $values -Entry $entry -SourceSlug "check_size_max_aed" -TargetSlug "check_size_max" -Kind currency -AedToUsd
    Add-EntryScalar -Target $values -Entry $entry -SourceSlug "ev_ceiling_aed" -TargetSlug "ev_ceiling" -Kind currency -AedToUsd
    Add-EntryScalar -Target $values -Entry $entry -SourceSlug "earnout_tolerance" -TargetSlug "earnout_tolerance"
    Add-EntryScalar -Target $values -Entry $entry -SourceSlug "profitable_companies_only_mandate" -TargetSlug "profitable_only"
    Add-EntryText -Target $values -Entry $entry -SourceSlug "investment_strategy" -TargetSlug "investment_strategy"
    Add-EntryText -Target $values -Entry $entry -SourceSlug "additional_notes" -TargetSlug "notes"
    # 2026-08-19 decision: live data is 274 of 275 Buyer Database entries
    # blank, and the one populated value is "Flexible", which already
    # matches a DEV option directly -- wired as a real mapping despite the
    # SOURCE (100% Cash/Cash + Seller Note/Earnout Considered/Flexible) and
    # DEV (Majority/Minority/Flexible/Acquisition Financing) option sets not
    # otherwise aligning. Revisit if SOURCE usage of the other 3 options grows.
    Add-EntryScalar -Target $values -Entry $entry -SourceSlug "deal_structure_tolerance" -TargetSlug "deal_structure_tolerance"
    Add-EntryScalar -Target $values -Entry $entry -SourceSlug "deals_introduced_count" -TargetSlug "deals_introduced"
    Add-EntryScalar -Target $values -Entry $entry -SourceSlug "deals_converted_count" -TargetSlug "deals_converted"
    Add-EntryScalar -Target $values -Entry $entry -SourceSlug "ebitda_ceiling_aed" -TargetSlug "ebitda_ceiling" -Kind currency -AedToUsd
    Add-EntryScalar -Target $values -Entry $entry -SourceSlug "estimated_aum_usd" -TargetSlug "estimated_aum" -Kind currency
    Add-EntryText -Target $values -Entry $entry -SourceSlug "notable_investments" -TargetSlug "notable_investments"
    Add-EntryText -Target $values -Entry $entry -SourceSlug "key_personnel" -TargetSlug "key_personnel"
    Add-EntryScalar -Target $values -Entry $entry -SourceSlug "relationship_warmth" -TargetSlug "relationship_warmth"
    Add-EntryScalar -Target $values -Entry $entry -SourceSlug "last_mandate_briefing_date" -TargetSlug "last_mandate_briefing_date"
    Add-EntryText -Target $values -Entry $entry -SourceSlug "prior_gcc_acquisition" -TargetSlug "prior_gcc_acquisition"
    $targetGeographyTitles = @(Get-EntryValueTitles -Entry $entry -Slug "target_geography")
    if ($targetGeographyTitles.Count -gt 0) { $values["target_geography"] = @($targetGeographyTitles) }
    $checkSizeTitles = @(Get-EntryValueTitles -Entry $entry -Slug "typical_check_size_7")

    # Backfill check_size_min/max from SOURCE's typical_check_size_7 when
    # SOURCE left them blank (2026-08-23 decision). typical_check_size_7 is a
    # coarse USD range bucket picked from a fixed 4-option set; check_size_min/max
    # are real, more-precise USD figures -- never overwrite an already-resolved
    # real value with this coarse approximation, only fill in whichever of
    # min/max SOURCE didn't provide. No currency conversion needed -- both
    # sides are USD as of the 2026-08-25 AED->USD cleanup (previously converted
    # at a fixed USD/AED peg, back when check_size_min/max were AED). Multiselect
    # -safe (the field allows it, even though no live entry currently selects
    # more than one): takes the envelope (lowest min, highest max) across every
    # option selected. DEV's own typical_check_size attribute was dropped
    # 2026-08-23 (redundant with check_size_min/max) -- this only ever reads
    # the SOURCE value now, never writes it back to DEV. See
    # migration-decisions.json's dropped_fields.
    if ($checkSizeTitles.Count -gt 0 -and (-not $values.ContainsKey("check_size_min") -or -not $values.ContainsKey("check_size_max"))) {
      $checkSizeRanges = @{
        'Under $1M' = @{ MinUsd = [decimal]0;        MaxUsd = [decimal]1000000 }
        '$1-5M'     = @{ MinUsd = [decimal]1000000;  MaxUsd = [decimal]5000000 }
        '$5-20M'    = @{ MinUsd = [decimal]5000000;  MaxUsd = [decimal]20000000 }
        '$20M+'     = @{ MinUsd = [decimal]20000000; MaxUsd = $null }
      }
      $mins = [Collections.Generic.List[decimal]]::new()
      $maxes = [Collections.Generic.List[decimal]]::new()
      $hasOpenEnded = $false
      foreach ($title in $checkSizeTitles) {
        if (-not $checkSizeRanges.ContainsKey($title)) { continue }
        $range = $checkSizeRanges[$title]
        $mins.Add($range.MinUsd)
        if ($null -eq $range.MaxUsd) { $hasOpenEnded = $true } else { $maxes.Add($range.MaxUsd) }
      }
      if ($mins.Count -gt 0 -and -not $values.ContainsKey("check_size_min")) {
        $values["check_size_min"] = @{ currency_value = ($mins | Measure-Object -Minimum).Minimum }
      }
      if (-not $hasOpenEnded -and $maxes.Count -gt 0 -and -not $values.ContainsKey("check_size_max")) {
        $values["check_size_max"] = @{ currency_value = ($maxes | Measure-Object -Maximum).Maximum }
      }
    }
    $values["is_active"] = $isActive
    $values["legacy_entry_id"] = $sourceEntryId

    $keyContactName = Get-Value -Values $entry.entry_values -Slug "key_personnel_email"
    $hasKeyContactName = -not [string]::IsNullOrWhiteSpace([string]$keyContactName)
    $keyContactResolution = if ($hasKeyContactName) { "unmatched" } else { "blank_source" }
    if ($hasKeyContactName) {
      $normalizedContact = Normalize-PersonName -Name ([string]$keyContactName)
      $teamMatches = @(
        @($sourceCompanyTeam[$sourceParentId]) | Where-Object {
          $sourcePersonById.ContainsKey($_) -and $sourcePersonById[$_].NormalizedName -eq $normalizedContact
        }
      )
      $contactTokens = @($normalizedContact -split " " | Where-Object { $_ })
      $teamFirstNameMatches = if ($contactTokens.Count -eq 1) {
        @(
          @($sourceCompanyTeam[$sourceParentId]) | Where-Object {
            if (-not $sourcePersonById.ContainsKey($_)) { return $false }
            $personTokens = @($sourcePersonById[$_].NormalizedName -split " " | Where-Object { $_ })
            return $personTokens.Count -gt 0 -and $personTokens[0] -eq $contactTokens[0]
          }
        )
      } else { @() }
      $globalMatches = if ($sourcePersonIdsByName.ContainsKey($normalizedContact)) {
        @($sourcePersonIdsByName[$normalizedContact].ToArray())
      } else { @() }
      $candidateIds = if ($teamMatches.Count -eq 1) {
        $keyContactResolution = "team_exact"
        $teamMatches
      } elseif ($teamFirstNameMatches.Count -eq 1) {
        $keyContactResolution = "team_unique_first_name"
        $teamFirstNameMatches
      } elseif ($globalMatches.Count -eq 1) {
        $keyContactResolution = "global_unique_exact"
        $globalMatches
      } elseif ($teamMatches.Count -gt 1 -or $teamFirstNameMatches.Count -gt 1 -or $globalMatches.Count -gt 1) {
        $keyContactResolution = "ambiguous_exact"
        @()
      } else { @() }
      $candidateIds = @($candidateIds)
      if ($candidateIds.Count -eq 1) {
        $sourcePersonId = [string]$candidateIds[0]
        if ($devPersonByLegacyId.ContainsKey($sourcePersonId)) {
          $values["key_contact"] = @{ target_object="person"; target_record_id=$devPersonByLegacyId[$sourcePersonId] }
        } else { $keyContactResolution = "missing_dev_person" }
      }
    }
    $plans.Add([pscustomobject]@{
      source_parent_id = $sourceParentId
      source_entry_id = $sourceEntryId
      dev_parent_id = $devParentId
      is_active = $isActive
      group_size = $entries.Count
      values = $values
      key_contact_name_count_pending_backfill = if ($hasKeyContactName) { 1 } else { 0 }
      key_contact_source = if ($hasKeyContactName) { [string]$keyContactName } else { $null }
      key_contact_resolution = $keyContactResolution
    })
  }
}

$existingEntries = @()
for ($offset = 0; ; $offset += 500) {
  $response = Invoke-AttioRequest -Method Post -Headers $devHeaders `
    -Path "/lists/buyer_role/entries/query" -Body @{ limit = 500; offset = $offset }
  $page = @($response.data)
  $existingEntries += $page
  if ($page.Count -lt 500) { break }
}

$existingByLegacyEntryId = @{}
$untaggedExistingByParent = @{}
foreach ($entry in $existingEntries) {
  $parentId = Get-ParentRecordId -Entry $entry
  $entryId = if ($entry.id.entry_id) { [string]$entry.id.entry_id } else { [string]$entry.entry_id }
  $legacyEntryId = Get-Value -Values $entry.entry_values -Slug "legacy_entry_id"
  if (-not [string]::IsNullOrWhiteSpace([string]$legacyEntryId)) {
    $existingByLegacyEntryId[[string]$legacyEntryId] = $entryId
  } elseif ($parentId) {
    # Pre-dates the is_active/legacy_entry_id fields: a single blended entry
    # from the old merge-by-parent logic. The group's active (newest) plan
    # claims it below and overwrites its blended values with its own raw
    # SOURCE row; older duplicates in the group always create fresh entries.
    if ($untaggedExistingByParent.ContainsKey($parentId)) {
      Write-Warning "buyer_role parent $parentId has more than one untagged legacy entry; only the first is auto-claimed."
    } else {
      $untaggedExistingByParent[$parentId] = $entryId
    }
  }
}

$applyStats = [ordered]@{ created = 0; updated = 0; errors = 0 }
if ($Apply) {
  $optionMaps = @{}
  $singleSelectFields = @("model", "mandate_status", "deal_structure_tolerance", "relationship_warmth")
  $multiSelectFields = @("target_geography")
  foreach ($field in $singleSelectFields + $multiSelectFields) {
    $response = Invoke-AttioRequest -Method Get -Headers $devHeaders `
      -Path "/lists/buyer_role/attributes/$field/options"
    $map = @{}
    foreach ($option in @($response.data | Where-Object { -not $_.is_archived })) {
      $map[[string]$option.title] = [string]$option.id.option_id
    }
    $optionMaps[$field] = $map
  }

  $selectedPlans = if ($Limit -eq 0) {
    @($plans)
  } else {
    @($plans | Select-Object -Skip $StartIndex -First $Limit)
  }
  foreach ($plan in $selectedPlans) {
    $payloadValues = @{}
    foreach ($key in $plan.values.Keys) {
      $payloadValues[$key] = $plan.values[$key]
    }
    foreach ($field in $singleSelectFields) {
      if ($payloadValues.ContainsKey($field)) {
        $title = [string]$payloadValues[$field]
        if (-not $optionMaps[$field].ContainsKey($title)) {
          throw "DEV buyer_role/$field option '$title' is missing."
        }
        $payloadValues[$field] = $optionMaps[$field][$title]
      }
    }
    foreach ($field in $multiSelectFields) {
      if ($payloadValues.ContainsKey($field)) {
        $ids = [Collections.Generic.List[string]]::new()
        foreach ($title in @($payloadValues[$field])) {
          $titleStr = [string]$title
          if (-not $optionMaps[$field].ContainsKey($titleStr)) {
            throw "DEV buyer_role/$field option '$titleStr' is missing."
          }
          $ids.Add($optionMaps[$field][$titleStr])
        }
        $payloadValues[$field] = @($ids)
      }
    }

    $targetEntryId = $null
    if ($existingByLegacyEntryId.ContainsKey($plan.source_entry_id)) {
      $targetEntryId = $existingByLegacyEntryId[$plan.source_entry_id]
    } elseif ($plan.is_active -and $untaggedExistingByParent.ContainsKey([string]$plan.dev_parent_id)) {
      $targetEntryId = $untaggedExistingByParent[[string]$plan.dev_parent_id]
      $untaggedExistingByParent.Remove([string]$plan.dev_parent_id)
    }

    try {
      if ($targetEntryId) {
        Invoke-AttioRequest -Method Patch -Headers $devHeaders `
          -Path "/lists/buyer_role/entries/$targetEntryId" `
          -Body @{ data = @{ entry_values = $payloadValues } } | Out-Null
        $existingByLegacyEntryId[$plan.source_entry_id] = $targetEntryId
        $applyStats.updated++
      } else {
        $created = Invoke-AttioRequest -Method Post -Headers $devHeaders `
          -Path "/lists/buyer_role/entries" -Body @{ data = @{
            parent_record_id = [string]$plan.dev_parent_id
            parent_object = "organizations"
            entry_values = $payloadValues
          } }
        $entryId = [string]$created.data.id.entry_id
        $existingByLegacyEntryId[$plan.source_entry_id] = $entryId
        $applyStats.created++
      }
    } catch {
      $applyStats.errors++
      throw
    }
  }
}

$summary = [ordered]@{
  generated_at_utc = [DateTime]::UtcNow.ToString("o")
  mode = if ($Apply) { "bounded-apply" } else { "dry-run" }
  source_entries = $sourceEntries.Count
  parent_groups = $groups.Count
  duplicate_parent_groups = @($groups | Where-Object Count -gt 1).Count
  resolved_plans = $plans.Count
  active_plans = @($plans | Where-Object is_active).Count
  inactive_plans = @($plans | Where-Object { -not $_.is_active }).Count
  unresolved_parents = $unresolvedParents.Count
  unresolved_parent_ids = @($unresolvedParents | Select-Object -Unique)
  key_contacts_pending_backfill = @(
    $plans | Where-Object { $_.key_contact_name_count_pending_backfill -gt 0 -and $_.key_contact_resolution -notin @("team_exact","team_unique_first_name","global_unique_exact") }
  ).Count
  key_contacts_resolved = @($plans | Where-Object { $_.key_contact_resolution -in @("team_exact","team_unique_first_name","global_unique_exact") }).Count
  existing_dev_entries = $existingEntries.Count
  applied_limit = if ($Apply -and $Limit -eq 0) { $plans.Count } elseif ($Apply) { $Limit } else { 0 }
  applied_start_index = if ($Apply) { $StartIndex } else { 0 }
  applied_created = $applyStats.created
  applied_updated = $applyStats.updated
  apply_errors = $applyStats.errors
}

$result = [ordered]@{
  summary = $summary
  sample = @($plans | Select-Object -First $SampleSize)
  plans = @($plans)
}

$directory = Split-Path $outputPath -Parent
[System.IO.Directory]::CreateDirectory($directory) | Out-Null
[System.IO.File]::WriteAllText(
  $outputPath,
  ($result | ConvertTo-Json -Depth 40),
  [System.Text.UTF8Encoding]::new($false)
)

$summary | Format-List
Write-Host "Buyer Role dry-run plan written to $outputPath"
if ($Apply) {
  Write-Host "Bounded Buyer Role apply complete. Created=$($applyStats.created), updated=$($applyStats.updated), errors=$($applyStats.errors)."
} else {
  Write-Host "No Attio records were written."
}

}
function Invoke-SellerRole {
param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [string]$DevApiKey = $env:DEV_ATTIO_API_KEY,
  [int]$SampleSize = 10,
  [ValidateRange(0, 1000000)]
  [int]$StartIndex = 0,
  [int]$Limit = 0,
  [string]$Confirmation,
  [switch]$Apply
)


$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($SourceApiKey)) {
  $SourceApiKey = [Environment]::GetEnvironmentVariable("SOURCE_ATTIO_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($DevApiKey)) {
  $DevApiKey = [Environment]::GetEnvironmentVariable("DEV_ATTIO_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($SourceApiKey)) { throw "Missing SOURCE_ATTIO_API_KEY." }
if ([string]::IsNullOrWhiteSpace($DevApiKey)) { throw "Missing DEV_ATTIO_API_KEY." }
if ($Apply) {
  $isBoundedApply = $Limit -ge 1 -and $Limit -le 10 -and
    $Confirmation -eq "APPLY_SELLER_ROLE_TO_DEV"
  $isFullApply = $Limit -eq 0 -and
    $Confirmation -eq "APPLY_ALL_SELLER_ROLE_TO_DEV"
  if (-not $isBoundedApply -and -not $isFullApply) {
    throw "Use a 1-10 limit with APPLY_SELLER_ROLE_TO_DEV, or Limit 0 with APPLY_ALL_SELLER_ROLE_TO_DEV."
  }
}

$sourceHeaders = @{
  Authorization = "Bearer $($SourceApiKey.Trim())"
  Accept = "application/json"
  "Content-Type" = "application/json"
}
$devHeaders = @{
  Authorization = "Bearer $($DevApiKey.Trim())"
  Accept = "application/json"
  "Content-Type" = "application/json"
}

$migrationRoot = Split-Path $PSScriptRoot -Parent
$decisions = Get-Content (Join-Path $migrationRoot "config\migration-decisions.json") -Raw |
  ConvertFrom-Json
$expectedWorkspaceId = [string]$decisions.dev_workspace_id
# Blank-duplicate SOURCE companies (a second lead-magnet submission for a
# company that already exists) that were never migrated into DEV
# Organizations and so block parent resolution below. SOURCE is read-only
# to this tooling, so the duplicate can't be repointed at the source --
# instead it's aliased here to the real, already-migrated SOURCE company id.
$duplicateCompanyAlias = @{}
if ($decisions.duplicate_source_company_ids.mapping) {
  foreach ($property in $decisions.duplicate_source_company_ids.mapping.PSObject.Properties) {
    $duplicateCompanyAlias[[string]$property.Name] = [string]$property.Value
  }
}
$outputPath = Join-Path $migrationRoot "..\..\..\outputs\attio_migration\seller-role-plan.json"

function Invoke-AttioRequest {
  param(
    [ValidateSet("Get", "Post", "Patch")][string]$Method,
    [hashtable]$Headers,
    [string]$Path,
    [object]$Body
  )
  $parameters = @{
    Method = $Method
    Uri = "https://api.attio.com/v2$Path"
    Headers = $Headers
  }
  if ($null -ne $Body) {
    $parameters.Body = [Text.Encoding]::UTF8.GetBytes(
      ($Body | ConvertTo-Json -Depth 30)
    )
  }
  Invoke-RestMethod @parameters
}

function Get-ParentRecordId {
  param([object]$Entry)
  if ($Entry.parent_record_id.record_id) { return [string]$Entry.parent_record_id.record_id }
  return [string]$Entry.parent_record_id
}

function Get-RecordId {
  param([object]$Record)
  if ($Record.id.record_id) { return [string]$Record.id.record_id }
  return [string]$Record.record_id
}

function Get-Value {
  param([object]$Values, [string]$Slug)
  $item = @($Values.$Slug) |
    Where-Object { $null -eq $_.active_until } |
    Select-Object -First 1
  if ($null -eq $item) { return $null }
  if ($null -ne $item.value) { return $item.value }
  if ($item.option.title) { return [string]$item.option.title }
  return $null
}

function Get-DistinctValues {
  param([object[]]$Entries, [string]$Slug)
  return @(
    $Entries |
      ForEach-Object { Get-Value -Values $_.entry_values -Slug $Slug } |
      Where-Object {
        $null -ne $_ -and
        (-not ($_ -is [string]) -or -not [string]::IsNullOrWhiteSpace($_))
      } |
      Sort-Object -Unique
  )
}

function Add-UniqueValue {
  param(
    [hashtable]$Target,
    [System.Collections.Generic.List[object]]$Conflicts,
    [object[]]$Entries,
    [string]$SourceSlug,
    [string]$TargetSlug,
    [switch]$Currency
  )
  $values = @(Get-DistinctValues -Entries $Entries -Slug $SourceSlug)
  if ($values.Count -eq 0) { return }
  if ($values.Count -gt 1) {
    $Conflicts.Add([pscustomobject]@{
      target_field = $TargetSlug
      reason = "multiple_distinct_nonblank_values"
      value_count = $values.Count
    })
    return
  }
  if ($Currency) {
    $Target[$TargetSlug] = @{ currency_value = [decimal]$values[0] }
  } else {
    $Target[$TargetSlug] = $values[0]
  }
}

function Add-EntryScalar {
  param(
    [hashtable]$Target,
    [object]$Entry,
    [string]$SourceSlug,
    [string]$TargetSlug,
    [switch]$Currency,
    # SOURCE's own *_aed fields are real AED figures; DEV's equivalent
    # currency attributes now default to USD (2026-08-25 cleanup) -- set this
    # so the migrated number is an actual USD-equivalent, not an AED number
    # under a USD label. Fixed peg (1 USD = 3.6725 AED), matching the rate
    # already used elsewhere in this file's check_size backfill.
    [switch]$AedToUsd
  )
  $raw = Get-Value -Values $Entry.entry_values -Slug $SourceSlug
  if ($null -eq $raw) { return }
  if ($raw -is [string]) {
    $raw = $raw.Trim()
    if ([string]::IsNullOrWhiteSpace($raw)) { return }
  }
  if ($Currency) {
    $amount = [decimal]$raw
    if ($AedToUsd) { $amount = [Math]::Round($amount / [decimal]3.6725, 2) }
    $Target[$TargetSlug] = @{ currency_value = $amount }
  } else {
    $Target[$TargetSlug] = $raw
  }
}

function Get-LatestAttempt {
  param([object[]]$Entries)
  $attempts = @(
    [pscustomobject]@{ Date="attempt_1_date"; Channel="attempt_1_channel"; Outcome="attempt_1_outcome" },
    [pscustomobject]@{ Date="attempt_2_date"; Channel="attempt_2_channel"; Outcome="attempt_2_outcome" },
    [pscustomobject]@{ Date="attempt_2_date_3"; Channel="attempt_2_channel_6"; Outcome="attempt_2_outcome_6" }
  )
  $candidates = @()
  foreach ($entry in $Entries) {
    foreach ($attempt in $attempts) {
      $dateText = Get-Value -Values $entry.entry_values -Slug $attempt.Date
      $parsed = [DateTime]::MinValue
      if ($dateText -and [DateTime]::TryParse([string]$dateText, [ref]$parsed)) {
        $candidates += [pscustomobject]@{
          Date = $parsed
          DateText = [string]$dateText
          Channel = Get-Value -Values $entry.entry_values -Slug $attempt.Channel
          Outcome = Get-Value -Values $entry.entry_values -Slug $attempt.Outcome
        }
      }
    }
  }
  return $candidates | Sort-Object Date -Descending | Select-Object -First 1
}

$devOrganization = Invoke-AttioRequest -Method Get -Headers $devHeaders `
  -Path "/objects/organizations"
$connectedWorkspaceId = [string]$devOrganization.data.id.workspace_id
if ($connectedWorkspaceId -ne $expectedWorkspaceId) {
  throw "DEV workspace mismatch. Expected $expectedWorkspaceId but connected to $connectedWorkspaceId."
}
$devSellerRole = Invoke-AttioRequest -Method Get -Headers $devHeaders `
  -Path "/lists/seller_role"
if (@($devSellerRole.data.parent_object) -notcontains "organizations") {
  throw "DEV seller_role is not parented to organizations."
}

$sourceEntries = @()
for ($offset = 0; ; $offset += 500) {
  $response = Invoke-AttioRequest -Method Post -Headers $sourceHeaders `
    -Path "/lists/valuation_tool_leads/entries/query" -Body @{ limit=500; offset=$offset }
  $page = @($response.data)
  $sourceEntries += $page
  if ($page.Count -lt 500) { break }
}

$devOrganizationByLegacyId = @{}
for ($offset = 0; ; $offset += 500) {
  $response = Invoke-AttioRequest -Method Post -Headers $devHeaders `
    -Path "/objects/organizations/records/query" -Body @{ limit=500; offset=$offset }
  $page = @($response.data)
  foreach ($record in $page) {
    $legacyId = Get-Value -Values $record.values -Slug "legacy_attio_id"
    if (-not [string]::IsNullOrWhiteSpace([string]$legacyId)) {
      if ($devOrganizationByLegacyId.ContainsKey([string]$legacyId)) {
        throw "DEV Organization legacy_attio_id is not unique."
      }
      $devOrganizationByLegacyId[[string]$legacyId] = Get-RecordId -Record $record
    }
  }
  if ($page.Count -lt 500) { break }
}

$plans = [System.Collections.Generic.List[object]]::new()
$unresolvedParents = [System.Collections.Generic.List[string]]::new()
$groups = @($sourceEntries | Group-Object { Get-ParentRecordId -Entry $_ })

foreach ($group in $groups) {
  $sourceParentId = [string]$group.Name
  if ($duplicateCompanyAlias.ContainsKey($sourceParentId)) { $sourceParentId = $duplicateCompanyAlias[$sourceParentId] }
  if (-not $devOrganizationByLegacyId.ContainsKey($sourceParentId)) {
    $unresolvedParents.Add($sourceParentId)
    continue
  }
  $devParentId = $devOrganizationByLegacyId[$sourceParentId]

  # Every raw SOURCE entry becomes its own DEV entry -- duplicates are no
  # longer merged. Sorted newest-first so entries[0] is the one flagged
  # is_active = true; every other duplicate in the group is is_active = false.
  $entries = @(@($group.Group) | Sort-Object { [datetime]$_.created_at } -Descending)

  for ($i = 0; $i -lt $entries.Count; $i++) {
    $entry = $entries[$i]
    $sourceEntryId = if ($entry.id.entry_id) { [string]$entry.id.entry_id } else { [string]$entry.entry_id }
    $isActive = ($i -eq 0)

    $values = @{}
    Add-EntryScalar $values $entry "outreach_tier" "outreach_tier"
    Add-EntryScalar $values $entry "seller_appetite_signal" "appetite_signal"
    Add-EntryScalar $values $entry "relationship_status" "relationship_status"
    Add-EntryScalar $values $entry "estimated_annual_revenue_aed" "est_revenue" -Currency -AedToUsd
    Add-EntryScalar $values $entry "estimated_ebitda_aed" "est_ebitda" -Currency -AedToUsd
    Add-EntryScalar $values $entry "outreach_score" "readiness_score"
    Add-EntryScalar $values $entry "re_engage_date" "re_engage_date"

    $latest = Get-LatestAttempt -Entries @($entry)
    if ($latest) {
      $values["last_attempt_date"] = $latest.DateText
      if ($latest.Channel) { $values["last_attempt_channel"] = $latest.Channel }
      if ($latest.Outcome) { $values["last_attempt_outcome"] = $latest.Outcome }
    }
    $values["is_active"] = $isActive
    $values["legacy_entry_id"] = $sourceEntryId

    $plans.Add([pscustomobject]@{
      source_parent_id = $sourceParentId
      source_entry_id = $sourceEntryId
      dev_parent_id = $devParentId
      is_active = $isActive
      group_size = $entries.Count
      values = $values
    })
  }
}

$existingEntries = @()
for ($offset = 0; ; $offset += 500) {
  $response = Invoke-AttioRequest -Method Post -Headers $devHeaders `
    -Path "/lists/seller_role/entries/query" -Body @{ limit=500; offset=$offset }
  $page = @($response.data)
  $existingEntries += $page
  if ($page.Count -lt 500) { break }
}
$existingByLegacyEntryId = @{}
$untaggedExistingByParent = @{}
foreach ($entry in $existingEntries) {
  $parentId = Get-ParentRecordId -Entry $entry
  $entryId = if ($entry.id.entry_id) { [string]$entry.id.entry_id } else { [string]$entry.entry_id }
  $legacyEntryId = Get-Value -Values $entry.entry_values -Slug "legacy_entry_id"
  if (-not [string]::IsNullOrWhiteSpace([string]$legacyEntryId)) {
    $existingByLegacyEntryId[[string]$legacyEntryId] = $entryId
  } elseif ($parentId) {
    # Pre-dates the is_active/legacy_entry_id fields: a single blended entry
    # from the old merge-by-parent logic. The group's active (newest) plan
    # claims it below and overwrites its blended values with its own raw
    # SOURCE row; older duplicates in the group always create fresh entries.
    if ($untaggedExistingByParent.ContainsKey($parentId)) {
      Write-Warning "seller_role parent $parentId has more than one untagged legacy entry; only the first is auto-claimed."
    } else {
      $untaggedExistingByParent[$parentId] = $entryId
    }
  }
}

$applyStats = [ordered]@{ created=0; updated=0; errors=0 }
if ($Apply) {
  if ($unresolvedParents.Count -gt 0) { throw "Refusing apply with unresolved parents." }

  $optionMaps = @{}
  foreach ($field in @("outreach_tier","appetite_signal","relationship_status","last_attempt_channel","last_attempt_outcome")) {
    $response = Invoke-AttioRequest -Method Get -Headers $devHeaders `
      -Path "/lists/seller_role/attributes/$field/options"
    $map = @{}
    foreach ($option in @($response.data | Where-Object { -not $_.is_archived })) {
      $map[[string]$option.title] = [string]$option.id.option_id
    }
    $optionMaps[$field] = $map
  }

  $selectedPlans = if ($Limit -eq 0) {
    @($plans)
  } else {
    @($plans | Select-Object -Skip $StartIndex -First $Limit)
  }
  foreach ($plan in $selectedPlans) {
    $payloadValues = @{}
    foreach ($key in $plan.values.Keys) { $payloadValues[$key] = $plan.values[$key] }
    foreach ($field in $optionMaps.Keys) {
      if ($payloadValues.ContainsKey($field)) {
        $title = [string]$payloadValues[$field]
        if (-not $optionMaps[$field].ContainsKey($title)) {
          throw "DEV seller_role/$field option '$title' is missing."
        }
        $payloadValues[$field] = $optionMaps[$field][$title]
      }
    }
    $targetEntryId = $null
    if ($existingByLegacyEntryId.ContainsKey($plan.source_entry_id)) {
      $targetEntryId = $existingByLegacyEntryId[$plan.source_entry_id]
    } elseif ($plan.is_active -and $untaggedExistingByParent.ContainsKey([string]$plan.dev_parent_id)) {
      $targetEntryId = $untaggedExistingByParent[[string]$plan.dev_parent_id]
      $untaggedExistingByParent.Remove([string]$plan.dev_parent_id)
    }

    try {
      if ($targetEntryId) {
        Invoke-AttioRequest -Method Patch -Headers $devHeaders `
          -Path "/lists/seller_role/entries/$targetEntryId" `
          -Body @{ data=@{ entry_values=$payloadValues } } | Out-Null
        $existingByLegacyEntryId[$plan.source_entry_id] = $targetEntryId
        $applyStats.updated++
      } else {
        $created = Invoke-AttioRequest -Method Post -Headers $devHeaders `
          -Path "/lists/seller_role/entries" -Body @{ data=@{
            parent_record_id = [string]$plan.dev_parent_id
            parent_object = "organizations"
            entry_values = $payloadValues
          } }
        $entryId = [string]$created.data.id.entry_id
        $existingByLegacyEntryId[$plan.source_entry_id] = $entryId
        $applyStats.created++
      }
    } catch {
      $applyStats.errors++
      throw
    }
  }
}

$summary = [ordered]@{
  generated_at_utc = [DateTime]::UtcNow.ToString("o")
  mode = if ($Apply) { "apply" } else { "dry-run" }
  source_entries = $sourceEntries.Count
  parent_groups = $groups.Count
  duplicate_parent_groups = @($groups | Where-Object Count -gt 1).Count
  resolved_plans = $plans.Count
  active_plans = @($plans | Where-Object is_active).Count
  inactive_plans = @($plans | Where-Object { -not $_.is_active }).Count
  unresolved_parents = $unresolvedParents.Count
  unresolved_parent_ids = @($unresolvedParents | Select-Object -Unique)
  existing_dev_entries = $existingEntries.Count
  applied_limit = if ($Apply -and $Limit -eq 0) { $plans.Count } elseif ($Apply) { $Limit } else { 0 }
  applied_created = $applyStats.created
  applied_updated = $applyStats.updated
  apply_errors = $applyStats.errors
}
$result = [ordered]@{
  summary = $summary
  sample = @($plans | Select-Object -First $SampleSize)
  plans = @($plans)
}
$directory = Split-Path $outputPath -Parent
[IO.Directory]::CreateDirectory($directory) | Out-Null
[IO.File]::WriteAllText(
  $outputPath,
  ($result | ConvertTo-Json -Depth 40),
  [Text.UTF8Encoding]::new($false)
)
$summary | Format-List
Write-Host "Seller Role plan written to $outputPath"
if ($Apply) {
  Write-Host "Seller Role apply complete. Created=$($applyStats.created), updated=$($applyStats.updated), errors=$($applyStats.errors)."
} else {
  Write-Host "No Attio records were written."
}

}
$a=@{SourceApiKey=$SourceApiKey;DevApiKey=$DevApiKey;SampleSize=$SampleSize;Limit=$Limit;Confirmation=$Confirmation};if($StartIndex){$a.StartIndex=$StartIndex};if($OutputSuffix){$a.OutputSuffix=$OutputSuffix};if($Apply){$a.Apply=$true}
switch($Task){"buyer_role"{Invoke-BuyerRole @a};"seller_role"{$a.Remove("OutputSuffix");Invoke-SellerRole @a}}
