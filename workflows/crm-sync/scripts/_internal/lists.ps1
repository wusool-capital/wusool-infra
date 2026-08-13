param(
 [ValidateSet("buyer_role","seller_role","mandates")][string]$Task,
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
  if (-not $devOrganizationByLegacyId.ContainsKey($sourceParentId)) {
    $unresolvedParents.Add($sourceParentId)
    continue
  }

  $values = @{}
  $conflicts = [System.Collections.Generic.List[object]]::new()
  $entries = @($group.Group)

  Add-UniqueScalar -Target $values -Conflicts $conflicts -Entries $entries `
    -SourceSlug "buyer_model" -TargetSlug "model"
  Add-UniqueScalar -Target $values -Conflicts $conflicts -Entries $entries `
    -SourceSlug "mandate_status" -TargetSlug "mandate_status"
  Add-UniqueScalar -Target $values -Conflicts $conflicts -Entries $entries `
    -SourceSlug "ebitda_floor_aed" -TargetSlug "ebitda_floor" -Kind currency
  Add-UniqueScalar -Target $values -Conflicts $conflicts -Entries $entries `
    -SourceSlug "check_size_min_aed" -TargetSlug "check_size_min" -Kind currency
  Add-UniqueScalar -Target $values -Conflicts $conflicts -Entries $entries `
    -SourceSlug "check_size_max_aed" -TargetSlug "check_size_max" -Kind currency
  Add-UniqueScalar -Target $values -Conflicts $conflicts -Entries $entries `
    -SourceSlug "ev_ceiling_aed" -TargetSlug "ev_ceiling" -Kind currency
  Add-UniqueScalar -Target $values -Conflicts $conflicts -Entries $entries `
    -SourceSlug "earnout_tolerance" -TargetSlug "earnout_tolerance"
  Add-UniqueScalar -Target $values -Conflicts $conflicts -Entries $entries `
    -SourceSlug "profitable_companies_only_mandate" -TargetSlug "profitable_only"
  Add-MergedText -Target $values -Entries $entries `
    -SourceSlug "investment_strategy" -TargetSlug "investment_strategy"
  Add-MergedText -Target $values -Entries $entries `
    -SourceSlug "additional_notes" -TargetSlug "notes"
  $dealStructureSourceValues = @(Get-DistinctValues -Entries $entries -Slug "deal_structure_tolerance")
  if ($dealStructureSourceValues.Count -gt 0) {
    $dealStructureNote = "SOURCE deal structure tolerance (pre-migration wording, not mapped to the new Majority/Minority/Flexible/Acquisition Financing options): " + ($dealStructureSourceValues -join "; ")
    $values["notes"] = if ($values.ContainsKey("notes")) { $values["notes"] + "`r`n`r`n" + $dealStructureNote } else { $dealStructureNote }
  }
  Add-UniqueScalar -Target $values -Conflicts $conflicts -Entries $entries `
    -SourceSlug "deals_introduced_count" -TargetSlug "deals_introduced"
  Add-UniqueScalar -Target $values -Conflicts $conflicts -Entries $entries `
    -SourceSlug "deals_converted_count" -TargetSlug "deals_converted"

  $keyContactNames = @(Get-DistinctValues -Entries $entries -Slug "key_personnel_email")
  $keyContactResolution = if ($keyContactNames.Count -eq 0) { "blank_source" } elseif ($keyContactNames.Count -gt 1) { "multiple_source_names" } else { "unmatched" }
  if ($keyContactNames.Count -eq 1) {
    $normalizedContact = Normalize-PersonName -Name ([string]$keyContactNames[0])
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
    dev_parent_id = $devOrganizationByLegacyId[$sourceParentId]
    merged_source_entry_count = $entries.Count
    values = $values
    conflicts = @($conflicts)
    key_contact_name_count_pending_backfill = $keyContactNames.Count
    key_contact_source = if ($keyContactNames.Count -eq 1) { [string]$keyContactNames[0] } else { $null }
    key_contact_resolution = $keyContactResolution
  })
}

$existingEntries = @()
for ($offset = 0; ; $offset += 500) {
  $response = Invoke-AttioRequest -Method Post -Headers $devHeaders `
    -Path "/lists/buyer_role/entries/query" -Body @{ limit = 500; offset = $offset }
  $page = @($response.data)
  $existingEntries += $page
  if ($page.Count -lt 500) { break }
}

$existingByParent = @{}
foreach ($entry in $existingEntries) {
  $parentId = Get-ParentRecordId -Entry $entry
  if ($parentId) {
    $entryId = if ($entry.id.entry_id) { [string]$entry.id.entry_id } else { [string]$entry.entry_id }
    $existingByParent[$parentId] = $entryId
  }
}

$applyStats = [ordered]@{ created = 0; updated = 0; errors = 0 }
if ($Apply) {
  $optionMaps = @{}
  foreach ($field in @("model", "mandate_status")) {
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
    if (@($plan.conflicts).Count -gt 0) {
      throw "Refusing to apply a Buyer Role plan containing scalar conflicts."
    }
    $payloadValues = @{}
    foreach ($key in $plan.values.Keys) {
      $payloadValues[$key] = $plan.values[$key]
    }
    foreach ($field in @("model", "mandate_status")) {
      if ($payloadValues.ContainsKey($field)) {
        $title = [string]$payloadValues[$field]
        if (-not $optionMaps[$field].ContainsKey($title)) {
          throw "DEV buyer_role/$field option '$title' is missing."
        }
        $payloadValues[$field] = $optionMaps[$field][$title]
      }
    }

    try {
      if ($existingByParent.ContainsKey([string]$plan.dev_parent_id)) {
        $entryId = $existingByParent[[string]$plan.dev_parent_id]
        Invoke-AttioRequest -Method Patch -Headers $devHeaders `
          -Path "/lists/buyer_role/entries/$entryId" `
          -Body @{ data = @{ entry_values = $payloadValues } } | Out-Null
        $applyStats.updated++
      } else {
        $created = Invoke-AttioRequest -Method Post -Headers $devHeaders `
          -Path "/lists/buyer_role/entries" -Body @{ data = @{
            parent_record_id = [string]$plan.dev_parent_id
            parent_object = "organizations"
            entry_values = $payloadValues
          } }
        $entryId = [string]$created.data.id.entry_id
        $existingByParent[[string]$plan.dev_parent_id] = $entryId
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
  canonical_parent_groups = $groups.Count
  duplicate_parent_groups = @($groups | Where-Object Count -gt 1).Count
  resolved_plans = $plans.Count
  unresolved_parents = $unresolvedParents.Count
  scalar_conflicts = @($plans | ForEach-Object { $_.conflicts }).Count
  key_contacts_pending_backfill = @(
    $plans | Where-Object { $_.key_contact_name_count_pending_backfill -gt 0 -and $_.key_contact_resolution -notin @("team_exact","team_unique_first_name","global_unique_exact") }
  ).Count
  key_contacts_resolved = @($plans | Where-Object { $_.key_contact_resolution -in @("team_exact","team_unique_first_name","global_unique_exact") }).Count
  existing_dev_entries = $existingEntries.Count
  would_create = if ($existingEntries.Count -eq 0) { $plans.Count } else { 0 }
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
  if (-not $devOrganizationByLegacyId.ContainsKey($sourceParentId)) {
    $unresolvedParents.Add($sourceParentId)
    continue
  }
  $values = @{}
  $conflicts = [System.Collections.Generic.List[object]]::new()
  $entries = @($group.Group)
  Add-UniqueValue $values $conflicts $entries "outreach_tier" "outreach_tier"
  Add-UniqueValue $values $conflicts $entries "seller_appetite_signal" "appetite_signal"
  Add-UniqueValue $values $conflicts $entries "relationship_status" "relationship_status"
  Add-UniqueValue $values $conflicts $entries "estimated_annual_revenue_aed" "est_revenue" -Currency
  Add-UniqueValue $values $conflicts $entries "estimated_ebitda_aed" "est_ebitda" -Currency
  Add-UniqueValue $values $conflicts $entries "outreach_score" "readiness_score"
  Add-UniqueValue $values $conflicts $entries "re_engage_date" "re_engage_date"

  $latest = Get-LatestAttempt -Entries $entries
  if ($latest) {
    $values["last_attempt_date"] = $latest.DateText
    if ($latest.Channel) { $values["last_attempt_channel"] = $latest.Channel }
    if ($latest.Outcome) { $values["last_attempt_outcome"] = $latest.Outcome }
  }

  $plans.Add([pscustomobject]@{
    source_parent_id = $sourceParentId
    dev_parent_id = $devOrganizationByLegacyId[$sourceParentId]
    merged_source_entry_count = $entries.Count
    values = $values
    conflicts = @($conflicts)
  })
}

$existingEntries = @()
for ($offset = 0; ; $offset += 500) {
  $response = Invoke-AttioRequest -Method Post -Headers $devHeaders `
    -Path "/lists/seller_role/entries/query" -Body @{ limit=500; offset=$offset }
  $page = @($response.data)
  $existingEntries += $page
  if ($page.Count -lt 500) { break }
}
$existingByParent = @{}
foreach ($entry in $existingEntries) {
  $parentId = Get-ParentRecordId -Entry $entry
  if ($parentId) {
    if ($existingByParent.ContainsKey($parentId)) {
      throw "DEV seller_role contains duplicate Organization parents."
    }
    $entryId = if ($entry.id.entry_id) { [string]$entry.id.entry_id } else { [string]$entry.entry_id }
    $existingByParent[$parentId] = $entryId
  }
}

$applyStats = [ordered]@{ created=0; updated=0; errors=0 }
if ($Apply) {
  if ($unresolvedParents.Count -gt 0) { throw "Refusing apply with unresolved parents." }
  if (@($plans | ForEach-Object { $_.conflicts }).Count -gt 0) {
    throw "Refusing apply because duplicate parents contain conflicting mapped values."
  }

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
    try {
      if ($existingByParent.ContainsKey([string]$plan.dev_parent_id)) {
        $entryId = $existingByParent[[string]$plan.dev_parent_id]
        Invoke-AttioRequest -Method Patch -Headers $devHeaders `
          -Path "/lists/seller_role/entries/$entryId" `
          -Body @{ data=@{ entry_values=$payloadValues } } | Out-Null
        $applyStats.updated++
      } else {
        $created = Invoke-AttioRequest -Method Post -Headers $devHeaders `
          -Path "/lists/seller_role/entries" -Body @{ data=@{
            parent_record_id = [string]$plan.dev_parent_id
            parent_object = "organizations"
            entry_values = $payloadValues
          } }
        $existingByParent[[string]$plan.dev_parent_id] = [string]$created.data.id.entry_id
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
  canonical_parent_groups = $groups.Count
  duplicate_parent_groups = @($groups | Where-Object Count -gt 1).Count
  resolved_plans = $plans.Count
  unresolved_parents = $unresolvedParents.Count
  scalar_conflicts = @($plans | ForEach-Object { $_.conflicts }).Count
  existing_dev_entries = $existingEntries.Count
  would_create = @($plans | Where-Object { -not $existingByParent.ContainsKey([string]$_.dev_parent_id) }).Count
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
function Invoke-Mandates {
param(
  [string]$SourceApiKey=$env:SOURCE_ATTIO_API_KEY,
  [string]$DevApiKey=$env:DEV_ATTIO_API_KEY,
  [int]$SampleSize=10,
  [int]$Limit=0,
  [string]$Confirmation,
  [switch]$Apply
)

$ErrorActionPreference="Stop"
if([string]::IsNullOrWhiteSpace($SourceApiKey)){$SourceApiKey=[Environment]::GetEnvironmentVariable("SOURCE_ATTIO_API_KEY","User")}
if([string]::IsNullOrWhiteSpace($DevApiKey)){$DevApiKey=[Environment]::GetEnvironmentVariable("DEV_ATTIO_API_KEY","User")}
if([string]::IsNullOrWhiteSpace($SourceApiKey)){throw "Missing SOURCE_ATTIO_API_KEY."}
if([string]::IsNullOrWhiteSpace($DevApiKey)){throw "Missing DEV_ATTIO_API_KEY."}
if($Apply){
  $bounded=$Limit-ge1-and$Limit-le10-and$Confirmation-eq"APPLY_MANDATES_TO_DEV"
  $full=$Limit-eq0-and$Confirmation-eq"APPLY_ALL_MANDATES_TO_DEV"
  if(-not$bounded-and-not$full){throw "Use a 1-10 limit with APPLY_MANDATES_TO_DEV, or Limit 0 with APPLY_ALL_MANDATES_TO_DEV."}
}
$sourceHeaders=@{Authorization="Bearer $($SourceApiKey.Trim())";Accept="application/json";"Content-Type"="application/json"}
$devHeaders=@{Authorization="Bearer $($DevApiKey.Trim())";Accept="application/json";"Content-Type"="application/json"}
$migrationRoot=Split-Path $PSScriptRoot -Parent
$decisions=Get-Content (Join-Path $migrationRoot "config\migration-decisions.json") -Raw|ConvertFrom-Json
$expectedWorkspaceId=[string]$decisions.dev_workspace_id
$outputPath=Join-Path $migrationRoot "..\..\..\outputs\attio_migration\mandates-plan.json"

function Invoke-AttioRequest{
  param([ValidateSet("Get","Post","Patch")][string]$Method,[hashtable]$Headers,[string]$Path,[object]$Body)
  $parameters=@{Method=$Method;Uri="https://api.attio.com/v2$Path";Headers=$Headers}
  if($null-ne$Body){$parameters.Body=[Text.Encoding]::UTF8.GetBytes(($Body|ConvertTo-Json -Depth 30))}
  Invoke-RestMethod @parameters
}
function Get-ParentId{
  param([object]$Entry)
  if($Entry.parent_record_id.record_id){return [string]$Entry.parent_record_id.record_id}
  return [string]$Entry.parent_record_id
}
function Get-RecordId{
  param([object]$Record)
  if($Record.id.record_id){return [string]$Record.id.record_id}
  return [string]$Record.record_id
}
function Get-Value{
  param([object]$Values,[string]$Slug)
  $item=@($Values.$Slug)|Where-Object{$null-eq$_.active_until}|Select-Object -First 1
  if($null-eq$item){return $null}
  if($null-ne$item.value){return $item.value}
  if($item.option.title){return [string]$item.option.title}
  return $null
}
function Add-Value{
  param([hashtable]$Target,[object]$Values,[string]$SourceSlug,[string]$TargetSlug)
  $value=Get-Value $Values $SourceSlug
  if($null-ne$value-and(-not($value-is[string])-or-not[string]::IsNullOrWhiteSpace($value))){$Target[$TargetSlug]=$value}
}

$devOrganization=Invoke-AttioRequest Get $devHeaders "/objects/organizations" $null
$connectedWorkspaceId=[string]$devOrganization.data.id.workspace_id
if($connectedWorkspaceId-ne$expectedWorkspaceId){throw "DEV workspace mismatch. Expected $expectedWorkspaceId but connected to $connectedWorkspaceId."}
$devMandates=Invoke-AttioRequest Get $devHeaders "/lists/mandates" $null
if(@($devMandates.data.parent_object)-notcontains"organizations"){throw "DEV mandates is not parented to organizations."}

$sourceEntries=@()
for($offset=0;;$offset+=500){
  $page=@((Invoke-AttioRequest Post $sourceHeaders "/lists/buy_side_mandates/entries/query" @{limit=500;offset=$offset}).data)
  $sourceEntries+=$page
  if($page.Count-lt500){break}
}
$devOrganizationByLegacyId=@{}
for($offset=0;;$offset+=500){
  $page=@((Invoke-AttioRequest Post $devHeaders "/objects/organizations/records/query" @{limit=500;offset=$offset}).data)
  foreach($record in $page){
    $legacyId=Get-Value $record.values "legacy_attio_id"
    if(-not[string]::IsNullOrWhiteSpace([string]$legacyId)){
      if($devOrganizationByLegacyId.ContainsKey([string]$legacyId)){throw "DEV Organization legacy_attio_id is not unique."}
      $devOrganizationByLegacyId[[string]$legacyId]=Get-RecordId $record
    }
  }
  if($page.Count-lt500){break}
}

$plans=[Collections.Generic.List[object]]::new()
$unresolved=[Collections.Generic.List[string]]::new()
$sourceGroups=@($sourceEntries|Group-Object{Get-ParentId $_})
foreach($group in $sourceGroups){
  $sourceParentId=[string]$group.Name
  if(-not$devOrganizationByLegacyId.ContainsKey($sourceParentId)){$unresolved.Add($sourceParentId);continue}
  if($group.Count-ne1){throw "SOURCE buy_side_mandates contains duplicate parent entries; merge rule required."}
  $entry=$group.Group[0]
  $devParentId=[string]$devOrganizationByLegacyId[$sourceParentId]
  $values=@{side="buy";buyer_id=$devParentId}
  Add-Value $values $entry.entry_values "mandate_phase" "phase"
  Add-Value $values $entry.entry_values "mandate_start_date" "start_date"
  Add-Value $values $entry.entry_values "mandate_expiry_date" "expiry_date"
  Add-Value $values $entry.entry_values "universe_constructed" "universe_constructed"
  Add-Value $values $entry.entry_values "shortlist_approved" "shortlist_approved"
  Add-Value $values $entry.entry_values "universe_size" "universe_size"
  Add-Value $values $entry.entry_values "shortlist_size" "shortlist_size"
  Add-Value $values $entry.entry_values "tier_1_targets_contacted" "tier1_contacted"
  Add-Value $values $entry.entry_values "responses_received" "responses"
  $plans.Add([pscustomobject]@{source_parent_id=$sourceParentId;dev_parent_id=$devParentId;values=$values})
}

$existingEntries=@()
for($offset=0;;$offset+=500){
  $page=@((Invoke-AttioRequest Post $devHeaders "/lists/mandates/entries/query" @{limit=500;offset=$offset}).data)
  $existingEntries+=$page
  if($page.Count-lt500){break}
}
$existingByParent=@{}
foreach($entry in $existingEntries){
  $parentId=Get-ParentId $entry
  if($existingByParent.ContainsKey($parentId)){throw "DEV mandates contains duplicate Organization parents."}
  $existingByParent[$parentId]=if($entry.id.entry_id){[string]$entry.id.entry_id}else{[string]$entry.entry_id}
}

$stats=[ordered]@{created=0;updated=0;errors=0}
if($Apply){
  if($unresolved.Count){throw "Refusing apply with unresolved parents."}
  $optionMaps=@{}
  foreach($field in @("side","phase")){
    $map=@{}
    $options=@((Invoke-AttioRequest Get $devHeaders "/lists/mandates/attributes/$field/options" $null).data)
    foreach($option in $options|Where-Object{-not$_.is_archived}){$map[[string]$option.title]=[string]$option.id.option_id}
    $optionMaps[$field]=$map
  }
  $selected=if($Limit-eq0){@($plans)}else{@($plans|Select-Object -First $Limit)}
  foreach($plan in $selected){
    $payload=@{};foreach($key in $plan.values.Keys){$payload[$key]=$plan.values[$key]}
    foreach($field in $optionMaps.Keys){
      if($payload.ContainsKey($field)){
        $title=[string]$payload[$field]
        if(-not$optionMaps[$field].ContainsKey($title)){throw "DEV mandates/$field option '$title' is missing."}
        $payload[$field]=$optionMaps[$field][$title]
      }
    }
    try{
      if($existingByParent.ContainsKey([string]$plan.dev_parent_id)){
        Invoke-AttioRequest Patch $devHeaders "/lists/mandates/entries/$($existingByParent[[string]$plan.dev_parent_id])" @{data=@{entry_values=$payload}}|Out-Null
        $stats.updated++
      }else{
        $created=Invoke-AttioRequest Post $devHeaders "/lists/mandates/entries" @{data=@{parent_record_id=[string]$plan.dev_parent_id;parent_object="organizations";entry_values=$payload}}
        $existingByParent[[string]$plan.dev_parent_id]=[string]$created.data.id.entry_id
        $stats.created++
      }
    }catch{$stats.errors++;throw}
  }
}
$summary=[ordered]@{
  generated_at_utc=[DateTime]::UtcNow.ToString("o");mode=if($Apply){"apply"}else{"dry-run"}
  source_entries=$sourceEntries.Count;canonical_parent_groups=$sourceGroups.Count;resolved_plans=$plans.Count
  unresolved_parents=$unresolved.Count;existing_dev_entries=$existingEntries.Count
  would_create=@($plans|Where-Object{-not$existingByParent.ContainsKey([string]$_.dev_parent_id)}).Count
  applied_created=$stats.created;applied_updated=$stats.updated;apply_errors=$stats.errors
}
$result=[ordered]@{summary=$summary;sample=@($plans|Select-Object -First $SampleSize);plans=@($plans)}
[IO.Directory]::CreateDirectory((Split-Path $outputPath -Parent))|Out-Null
[IO.File]::WriteAllText($outputPath,($result|ConvertTo-Json -Depth 40),[Text.UTF8Encoding]::new($false))
$summary|Format-List
Write-Host "Mandates plan written to $outputPath"
if($Apply){Write-Host "Mandates apply complete. Created=$($stats.created), updated=$($stats.updated), errors=$($stats.errors)."}else{Write-Host "No Attio records were written."}

}
$a=@{SourceApiKey=$SourceApiKey;DevApiKey=$DevApiKey;SampleSize=$SampleSize;Limit=$Limit;Confirmation=$Confirmation};if($StartIndex){$a.StartIndex=$StartIndex};if($OutputSuffix){$a.OutputSuffix=$OutputSuffix};if($Apply){$a.Apply=$true}
switch($Task){"buyer_role"{Invoke-BuyerRole @a};"seller_role"{$a.Remove("OutputSuffix");Invoke-SellerRole @a};"mandates"{$a.Remove("StartIndex");$a.Remove("OutputSuffix");Invoke-Mandates @a}}
