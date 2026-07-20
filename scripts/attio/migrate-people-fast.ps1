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

function Get-FirstEmail {
  param([object]$Values)

  $items = @($Values.email_addresses)
  if ($items.Count -eq 0) {
    return $null
  }

  return $items[0].email_address
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

$existingPeople = Get-ExistingLegacyIds -Object "people"
$existingCompanies = Get-ExistingLegacyIds -Object "companies"
Write-Host "Indexed $($existingPeople.Count) DEV people and $($existingCompanies.Count) DEV companies."

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

  Write-Host "Reading SOURCE people offset=$offset limit=$currentLimit"
  $sourceRecords = Invoke-AttioPost `
    -Headers $sourceHeaders `
    -Path "/objects/people/records/query" `
    -Body @{ limit = $currentLimit; offset = $offset }

  $records = @($sourceRecords.data)
  if ($records.Count -eq 0) {
    break
  }

  foreach ($record in $records) {
    $sourceId = $record.id.record_id
    $values = $record.values

    if ($existingPeople.ContainsKey($sourceId)) {
      $skippedCount++
      continue
    }

    $name = Get-FirstValue -Values $values -Slug "name"
    $email = Get-FirstEmail -Values $values

    if ([string]::IsNullOrWhiteSpace($name) -and [string]::IsNullOrWhiteSpace($email)) {
      if ($UseFallbackNames) {
        $name = "Unknown Source Person $sourceId"
        Write-Warning "Source person $sourceId has empty name and email. Using fallback name '$name'."
      } else {
        Write-Warning "Skipping source person $sourceId because name and email are empty."
        $skippedCount++
        continue
      }
    }

    $payloadValues = @{
      legacy_attio_id = $sourceId
    }

    if (-not [string]::IsNullOrWhiteSpace($name)) {
      $payloadValues.name = $name
    }

    if (-not [string]::IsNullOrWhiteSpace($email)) {
      $payloadValues.email_addresses = @($email)
    }

    foreach ($textSlug in @("job_title", "description", "linkedin", "notes")) {
      $textValue = Get-FirstValue -Values $values -Slug $textSlug
      if (-not [string]::IsNullOrWhiteSpace($textValue)) {
        $payloadValues[$textSlug] = $textValue
      }
    }

    $sourceCompanyRef = @($values.company) | Select-Object -First 1
    if ($sourceCompanyRef -and $sourceCompanyRef.target_record_id) {
      $sourceCompanyId = $sourceCompanyRef.target_record_id
      if ($existingCompanies.ContainsKey($sourceCompanyId)) {
        $payloadValues.company = @($existingCompanies[$sourceCompanyId])
      } else {
        Write-Warning "Person '$name' references source company $sourceCompanyId, but that company is not migrated to DEV yet. Skipping company link."
      }
    }

    if (-not $Apply) {
      Write-Host "DRY RUN: would create person '$name' <$email> ($sourceId)"
      $skippedCount++
      continue
    }

    $body = @{
      data = @{
        values = $payloadValues
      }
    }

    try {
      $created = Invoke-AttioPost -Headers $devHeaders -Path "/objects/people/records" -Body $body
      $devRecordId = $created.data.id.record_id
      $existingPeople[$sourceId] = $devRecordId
      $createdCount++
      Write-Host "Created DEV person '$name' ($devRecordId)"
    } catch {
      Write-Warning "Failed to create person '$name' <$email> ($sourceId). $($_.ErrorDetails.Message)"
      $errorCount++
    }
  }

  if ($records.Count -lt $currentLimit) {
    break
  }
}

Write-Host "Fast people migration complete. Created: $createdCount; skipped existing/invalid: $skippedCount; errors: $errorCount"
