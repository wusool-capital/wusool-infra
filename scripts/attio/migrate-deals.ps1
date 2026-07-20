param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [string]$DevApiKey = $env:DEV_ATTIO_API_KEY,
  [string]$DevOwnerWorkspaceMemberId = $env:DEV_ATTIO_OWNER_WORKSPACE_MEMBER_ID,
  [int]$Limit = 1,
  [int]$Offset = 0,
  [switch]$IncludeCurrency,
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

function Invoke-AttioPut {
  param(
    [hashtable]$Headers,
    [string]$Path,
    [object]$Body
  )

  Invoke-RestMethod `
    -Method Put `
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

function Get-FirstStatusTitle {
  param(
    [object]$Values,
    [string]$Slug
  )

  $items = @($Values.$Slug)
  if ($items.Count -eq 0 -or -not $items[0].status.title) {
    return $null
  }

  return $items[0].status.title
}

function Find-DevRecordByLegacyId {
  param(
    [string]$Object,
    [string]$LegacyId
  )

  $body = @{
    filter = @{
      legacy_attio_id = $LegacyId
    }
    limit = 1
  }

  try {
    $result = Invoke-AttioPost -Headers $devHeaders -Path "/objects/$Object/records/query" -Body $body
    return @($result.data) | Select-Object -First 1
  } catch {
    Write-Warning "Could not query DEV $Object by legacy_attio_id. $($_.ErrorDetails.Message)"
    return $null
  }
}

$sourceRecords = Invoke-AttioPost `
  -Headers $sourceHeaders `
  -Path "/objects/deals/records/query" `
  -Body @{ limit = $Limit; offset = $Offset }

$migrated = 0
$skipped = 0

foreach ($record in @($sourceRecords.data)) {
  $sourceId = $record.id.record_id
  $values = $record.values
  $name = Get-FirstValue -Values $values -Slug "name"

  if ([string]::IsNullOrWhiteSpace($name)) {
    Write-Warning "Skipping source deal $sourceId because name is empty."
    $skipped++
    continue
  }

  $payloadValues = @{
    legacy_attio_id = $sourceId
    name            = $name
  }

  if (-not [string]::IsNullOrWhiteSpace($DevOwnerWorkspaceMemberId)) {
    $payloadValues.owner = @{
      referenced_actor_type = "workspace-member"
      referenced_actor_id   = $DevOwnerWorkspaceMemberId
    }
  }

  $stage = Get-FirstStatusTitle -Values $values -Slug "stage"
  if (-not [string]::IsNullOrWhiteSpace($stage)) {
    $payloadValues.stage = $stage
  } else {
    $payloadValues.stage = "Inbound"
  }

  $sourceCompanyRef = @($values.associated_company) | Select-Object -First 1
  if ($sourceCompanyRef -and $sourceCompanyRef.target_record_id) {
    $devCompany = Find-DevRecordByLegacyId -Object "companies" -LegacyId $sourceCompanyRef.target_record_id
    if ($devCompany) {
      $payloadValues.associated_company = @($devCompany.id.record_id)
    } else {
      Write-Warning "Deal '$name' references source company $($sourceCompanyRef.target_record_id), but that company is not migrated to DEV yet. Skipping company link."
    }
  }

  if ($IncludeCurrency) {
    $value = @($values.value) | Select-Object -First 1
    if ($value -and $value.currency_value) {
      $payloadValues.value = $value.currency_value
    }
  }

  $existing = Find-DevRecordByLegacyId -Object "deals" -LegacyId $sourceId
  $body = @{
    data = @{
      values = $payloadValues
    }
  }

  if (-not $Apply) {
    $action = if ($existing) { "update" } else { "create" }
    Write-Host "DRY RUN: would $action deal '$name' ($sourceId)"
    continue
  }

  if ($existing) {
    $devRecordId = $existing.id.record_id
    Invoke-AttioPut -Headers $devHeaders -Path "/objects/deals/records/$devRecordId" -Body $body | Out-Null
    Write-Host "Updated DEV deal '$name' ($devRecordId)"
  } else {
    $created = Invoke-AttioPost -Headers $devHeaders -Path "/objects/deals/records" -Body $body
    Write-Host "Created DEV deal '$name' ($($created.data.id.record_id))"
  }

  $migrated++
}

if (-not $Apply) {
  Write-Host "Dry run complete. Add -Apply to create/update DEV deals."
} else {
  Write-Host "Deal migration complete. Migrated: $migrated; skipped: $skipped"
}
