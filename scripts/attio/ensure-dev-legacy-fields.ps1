param(
  [string]$DevApiKey = $env:DEV_ATTIO_API_KEY,
  [string[]]$Objects = @("companies", "people", "deals", "scorecards")
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($DevApiKey)) {
  throw "Missing DEV_ATTIO_API_KEY. Set it as an environment variable or pass -DevApiKey."
}

$headers = @{
  Authorization  = "Bearer $DevApiKey"
  Accept         = "application/json"
  "Content-Type" = "application/json"
}

function Invoke-AttioGet {
  param([string]$Path)
  Invoke-RestMethod -Method Get -Uri "https://api.attio.com/v2$Path" -Headers $headers
}

function Invoke-AttioPost {
  param(
    [string]$Path,
    [object]$Body
  )

  Invoke-RestMethod `
    -Method Post `
    -Uri "https://api.attio.com/v2$Path" `
    -Headers $headers `
    -Body ($Body | ConvertTo-Json -Depth 50)
}

foreach ($object in $Objects) {
  Write-Host "Checking $object legacy_attio_id"
  try {
    $attributes = Invoke-AttioGet -Path "/objects/$object/attributes"
  } catch {
    Write-Warning "Skipping $object because Attio returned an error. The object may be disabled or unavailable in this workspace. $($_.Exception.Message)"
    continue
  }

  $attributeJson = $attributes | ConvertTo-Json -Depth 100
  $existing = $attributeJson -match '"legacy_attio_id"'

  if ($existing) {
    Write-Host "legacy_attio_id already exists on $object"
    continue
  }

  $body = @{
    data = @{
      title          = "Legacy Attio ID"
      description    = "Source workspace Attio record ID used for safe, idempotent CRM migration."
      api_slug       = "legacy_attio_id"
      type           = "text"
      is_required    = $false
      is_unique      = $false
      is_multiselect = $false
      config         = @{}
    }
  }

  try {
    Invoke-AttioPost -Path "/objects/$object/attributes" -Body $body | Out-Null
    Write-Host "Created legacy_attio_id on $object"
  } catch {
    $errorBody = $_.ErrorDetails.Message
    if ($errorBody -match "slug_conflict") {
      Write-Host "legacy_attio_id already exists on $object"
      continue
    }

    throw
  }
}

Write-Host "DEV legacy fields check complete."
