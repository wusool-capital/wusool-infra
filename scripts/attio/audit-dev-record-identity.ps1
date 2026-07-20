param(
  [string]$DevApiKey = $env:DEV_ATTIO_API_KEY,
  [string[]]$Objects = @("companies", "people", "deals"),
  [int]$Limit = 500
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($DevApiKey)) {
  throw "Missing DEV_ATTIO_API_KEY."
}

$headers = @{
  Authorization  = "Bearer $DevApiKey"
  Accept         = "application/json"
  "Content-Type" = "application/json"
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

$rows = @()

foreach ($object in $Objects) {
  $offset = 0
  $total = 0
  $withLegacy = 0
  $withoutLegacy = 0
  $legacyIds = @{}
  $duplicateLegacyIds = 0

  while ($true) {
    $result = Invoke-AttioPost `
      -Path "/objects/$object/records/query" `
      -Body @{ limit = $Limit; offset = $offset }

    $records = @($result.data)
    foreach ($record in $records) {
      $total++
      $legacyId = Get-FirstValue -Values $record.values -Slug "legacy_attio_id"

      if ([string]::IsNullOrWhiteSpace($legacyId)) {
        $withoutLegacy++
      } else {
        $withLegacy++
        if ($legacyIds.ContainsKey($legacyId)) {
          $duplicateLegacyIds++
        } else {
          $legacyIds[$legacyId] = $true
        }
      }
    }

    if ($records.Count -lt $Limit) {
      break
    }

    $offset += $Limit
  }

  $rows += [pscustomobject]@{
    object               = $object
    total                = $total
    with_legacy_attio_id = $withLegacy
    without_legacy_id    = $withoutLegacy
    duplicate_legacy_ids = $duplicateLegacyIds
  }
}

$rows | Format-Table -AutoSize
