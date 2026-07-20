param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [string]$DevApiKey = $env:DEV_ATTIO_API_KEY,
  [int]$Limit = 500,
  [int]$StartOffset = 0,
  [int]$MaxRecords = 0,
  [switch]$UseFallbackNames,
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

function Get-Domains {
  param([object]$Values)

  @($Values.domains) |
    Where-Object { $_.domain } |
    ForEach-Object { $_.domain }
}

function Get-ExistingDevCompanyLegacyIds {
  $existing = @{}
  $offset = 0
  $pageSize = 500

  while ($true) {
    Write-Host "Indexing DEV companies offset=$offset"
    $result = Invoke-AttioPost `
      -Headers $devHeaders `
      -Path "/objects/companies/records/query" `
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

$existingLegacyIds = Get-ExistingDevCompanyLegacyIds
Write-Host "Indexed $($existingLegacyIds.Count) DEV companies with legacy_attio_id."

$endOffset = [int]::MaxValue
if ($MaxRecords -gt 0) {
  $endOffset = $StartOffset + $MaxRecords
}

$createdCount = 0
$skippedCount = 0
$errorCount = 0

for ($offset = $StartOffset; $offset -lt $endOffset; $offset += $Limit) {
  $currentLimit = $Limit
  if ($MaxRecords -gt 0) {
    $remaining = $endOffset - $offset
    if ($remaining -le 0) {
      break
    }
    $currentLimit = [Math]::Min($Limit, $remaining)
  }

  Write-Host "Reading SOURCE companies offset=$offset limit=$currentLimit"
  $sourceRecords = Invoke-AttioPost `
    -Headers $sourceHeaders `
    -Path "/objects/companies/records/query" `
    -Body @{ limit = $currentLimit; offset = $offset }

  $records = @($sourceRecords.data)
  if ($records.Count -eq 0) {
    break
  }

  foreach ($record in $records) {
    $sourceId = $record.id.record_id
    $values = $record.values

    if ($existingLegacyIds.ContainsKey($sourceId)) {
      $skippedCount++
      continue
    }

    $name = Get-FirstValue -Values $values -Slug "name"
    if ([string]::IsNullOrWhiteSpace($name)) {
      if ($UseFallbackNames) {
        $name = "Unknown Source Company $sourceId"
        Write-Warning "Source company $sourceId has empty name. Using fallback name '$name'."
      } else {
        Write-Warning "Skipping source company $sourceId because name is empty."
        $skippedCount++
        continue
      }
    }

    $payloadValues = @{
      legacy_attio_id = $sourceId
      name            = $name
    }

    $description = Get-FirstValue -Values $values -Slug "description"
    if (-not [string]::IsNullOrWhiteSpace($description)) {
      $payloadValues.description = $description
    }

    $domains = @(Get-Domains -Values $values)
    if ($domains.Count -gt 0) {
      $payloadValues.domains = $domains
    }

    foreach ($textSlug in @("notes", "ticket_size", "linkedin", "facebook", "instagram", "twitter")) {
      $textValue = Get-FirstValue -Values $values -Slug $textSlug
      if (-not [string]::IsNullOrWhiteSpace($textValue)) {
        $payloadValues[$textSlug] = $textValue
      }
    }

    if (-not $Apply) {
      Write-Host "DRY RUN: would create company '$name' ($sourceId)"
      $skippedCount++
      continue
    }

    $body = @{
      data = @{
        values = $payloadValues
      }
    }

    try {
      $created = Invoke-AttioPost -Headers $devHeaders -Path "/objects/companies/records" -Body $body
      $devRecordId = $created.data.id.record_id
      $existingLegacyIds[$sourceId] = $devRecordId
      $createdCount++
      Write-Host "Created DEV company '$name' ($devRecordId)"
    } catch {
      $errorBody = $_.ErrorDetails.Message
      if ($errorBody -match "uniqueness_conflict" -and $payloadValues.ContainsKey("domains")) {
        Write-Warning "Domain conflict for company '$name' ($sourceId). Retrying without domains."
        $payloadValues.Remove("domains")
        $body = @{
          data = @{
            values = $payloadValues
          }
        }

        try {
          $created = Invoke-AttioPost -Headers $devHeaders -Path "/objects/companies/records" -Body $body
          $devRecordId = $created.data.id.record_id
          $existingLegacyIds[$sourceId] = $devRecordId
          $createdCount++
          Write-Host "Created DEV company '$name' without domains ($devRecordId)"
        } catch {
          Write-Warning "Failed to create company '$name' without domains ($sourceId). $($_.ErrorDetails.Message)"
          $errorCount++
        }
      } else {
        Write-Warning "Failed to create company '$name' ($sourceId). $errorBody"
        $errorCount++
      }
    }
  }

  if ($records.Count -lt $currentLimit) {
    break
  }
}

Write-Host "Fast company migration complete. Created: $createdCount; skipped existing/invalid: $skippedCount; errors: $errorCount"
