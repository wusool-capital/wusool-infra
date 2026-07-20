param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [string]$DevApiKey = $env:DEV_ATTIO_API_KEY,
  [string[]]$Lists = @("buyer_brain", "valuation_tool_leads", "buy_side_mandates"),
  [int]$Limit = 500,
  [switch]$Apply
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($SourceApiKey)) {
  throw "Missing SOURCE_ATTIO_API_KEY."
}

if ([string]::IsNullOrWhiteSpace($DevApiKey)) {
  throw "Missing DEV_ATTIO_API_KEY."
}

$sourceHeaders = @{
  Authorization  = "Bearer $SourceApiKey"
  Accept         = "application/json"
  "Content-Type" = "application/json"
}

$devHeaders = @{
  Authorization  = "Bearer $DevApiKey"
  Accept         = "application/json"
  "Content-Type" = "application/json"
}

function Invoke-AttioPost {
  param(
    [hashtable]$Headers,
    [string]$Path,
    [object]$Body
  )

  Invoke-RestMethod `
    -Method Post `
    -Uri "https://api.attio.com/v2$Path" `
    -Headers $Headers `
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

function Get-EntryParentRecordId {
  param([object]$Entry)

  if ($Entry.parent_record_id) {
    return $Entry.parent_record_id
  }

  if ($Entry.parent_record_id.record_id) {
    return $Entry.parent_record_id.record_id
  }

  if ($Entry.id.record_id) {
    return $Entry.id.record_id
  }

  if ($Entry.record_id) {
    return $Entry.record_id
  }

  return $null
}

function Get-ExistingLegacyIds {
  param([string]$Object)

  $existing = @{}
  $offset = 0
  $pageSize = 500

  while ($true) {
    Write-Host "Indexing DEV $Object offset=$offset"
    $result = Invoke-AttioPost `
      -Headers $devHeaders `
      -Path "/objects/$Object/records/query" `
      -Body @{ limit = $pageSize; offset = $offset }

    $records = @($result.data)
    foreach ($record in $records) {
      $legacyId = Get-FirstValue -Values $record.values -Slug "legacy_attio_id"
      if (-not [string]::IsNullOrWhiteSpace($legacyId)) {
        $existing[$legacyId] = $record.id.record_id
      }
    }

    if ($records.Count -lt $pageSize) {
      break
    }

    $offset += $pageSize
  }

  return $existing
}

function Get-ExistingDevListParents {
  param([string]$List)

  $existing = @{}
  $offset = 0

  while ($true) {
    Write-Host "Indexing DEV list $List offset=$offset"
    $result = Invoke-AttioPost `
      -Headers $devHeaders `
      -Path "/lists/$List/entries/query" `
      -Body @{ limit = $Limit; offset = $offset }

    $entries = @($result.data)
    foreach ($entry in $entries) {
      $parentId = Get-EntryParentRecordId -Entry $entry
      if (-not [string]::IsNullOrWhiteSpace($parentId)) {
        $existing[$parentId] = $true
      }
    }

    if ($entries.Count -lt $Limit) {
      break
    }

    $offset += $Limit
  }

  return $existing
}

$devCompaniesByLegacyId = Get-ExistingLegacyIds -Object "companies"
Write-Host "Indexed $($devCompaniesByLegacyId.Count) DEV companies by legacy_attio_id."

$totalCreated = 0
$totalSkipped = 0
$totalErrors = 0

foreach ($list in $Lists) {
  Write-Host "Migrating list entries for $list"
  $existingDevParents = Get-ExistingDevListParents -List $list
  $offset = 0
  $created = 0
  $skipped = 0
  $errors = 0

  while ($true) {
    Write-Host "Reading SOURCE list $list offset=$offset"
    $sourceEntries = Invoke-AttioPost `
      -Headers $sourceHeaders `
      -Path "/lists/$list/entries/query" `
      -Body @{ limit = $Limit; offset = $offset }

    $entries = @($sourceEntries.data)
    if ($entries.Count -eq 0) {
      break
    }

    foreach ($entry in $entries) {
      $sourceParentId = Get-EntryParentRecordId -Entry $entry
      if ([string]::IsNullOrWhiteSpace($sourceParentId)) {
        Write-Warning "Skipping $list entry because parent record ID could not be read."
        $skipped++
        continue
      }

      if (-not $devCompaniesByLegacyId.ContainsKey($sourceParentId)) {
        Write-Warning "Skipping $list entry for source company $sourceParentId because matching DEV company was not found."
        $skipped++
        continue
      }

      $devCompanyId = $devCompaniesByLegacyId[$sourceParentId]
      if ($existingDevParents.ContainsKey($devCompanyId)) {
        $skipped++
        continue
      }

      if (-not $Apply) {
        Write-Host "DRY RUN: would add DEV company $devCompanyId to $list"
        $skipped++
        continue
      }

      try {
        Invoke-AttioPost `
          -Headers $devHeaders `
          -Path "/lists/$list/entries" `
          -Body @{
            data = @{
              parent_object    = "companies"
              parent_record_id = $devCompanyId
              entry_values     = @{}
            }
          } | Out-Null

        $existingDevParents[$devCompanyId] = $true
        $created++
        Write-Host "Added DEV company $devCompanyId to $list"
      } catch {
        Write-Warning "Failed to add DEV company $devCompanyId to $list. $($_.ErrorDetails.Message)"
        $errors++
      }
    }

    if ($entries.Count -lt $Limit) {
      break
    }

    $offset += $Limit
  }

  $totalCreated += $created
  $totalSkipped += $skipped
  $totalErrors += $errors
  Write-Host "List $list complete. Created: $created; skipped: $skipped; errors: $errors"
}

Write-Host "List entry migration complete. Created: $totalCreated; skipped: $totalSkipped; errors: $totalErrors"
