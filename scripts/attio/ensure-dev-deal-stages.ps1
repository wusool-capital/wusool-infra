param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [string]$DevApiKey = $env:DEV_ATTIO_API_KEY
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

function Invoke-AttioGet {
  param(
    [hashtable]$Headers,
    [string]$Path
  )

  Invoke-RestMethod -Method Get -Uri "https://api.attio.com/v2$Path" -Headers $Headers
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
    -Body ($Body | ConvertTo-Json -Depth 50)
}

$sourceStatuses = Invoke-AttioGet -Headers $sourceHeaders -Path "/objects/deals/attributes/stage/statuses"
$devStatuses = Invoke-AttioGet -Headers $devHeaders -Path "/objects/deals/attributes/stage/statuses"
$devTitles = @($devStatuses.data | Where-Object { -not $_.is_archived } | ForEach-Object { $_.title })

foreach ($status in @($sourceStatuses.data | Where-Object { -not $_.is_archived })) {
  if ($devTitles -contains $status.title) {
    Write-Host "Deal stage exists: $($status.title)"
    continue
  }

  $body = @{
    data = @{
      title                 = $status.title
      celebration_enabled   = [bool]$status.celebration_enabled
      target_time_in_status = $status.target_time_in_status
    }
  }

  try {
    Invoke-AttioPost -Headers $devHeaders -Path "/objects/deals/attributes/stage/statuses" -Body $body | Out-Null
    Write-Host "Created deal stage: $($status.title)"
  } catch {
    $errorBody = $_.ErrorDetails.Message
    if ($errorBody -match "already|conflict") {
      Write-Host "Deal stage exists: $($status.title)"
    } else {
      Write-Warning "Failed to create deal stage $($status.title). $errorBody"
    }
  }
}

Write-Host "DEV deal stage ensure complete."
