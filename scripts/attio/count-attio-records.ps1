param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [string]$DevApiKey = $env:DEV_ATTIO_API_KEY,
  [ValidateSet("source", "dev", "both")]
  [string]$Workspace = "both",
  [string[]]$Objects = @("companies", "people", "deals")
)

$ErrorActionPreference = "Stop"

function Invoke-AttioPost {
  param(
    [string]$ApiKey,
    [string]$Path,
    [object]$Body
  )

  $headers = @{
    Authorization  = "Bearer $ApiKey"
    Accept         = "application/json"
    "Content-Type" = "application/json"
  }

  Invoke-RestMethod `
    -Method Post `
    -Uri "https://api.attio.com/v2$Path" `
    -Headers $headers `
    -Body ([System.Text.Encoding]::UTF8.GetBytes(($Body | ConvertTo-Json -Depth 50)))
}

function Get-Count {
  param(
    [string]$ApiKey,
    [string]$Object,
    [int]$PageSize = 100
  )

  $offset = 0
  $count = 0

  while ($true) {
    $result = Invoke-AttioPost `
      -ApiKey $ApiKey `
      -Path "/objects/$Object/records/query" `
      -Body @{ limit = $PageSize; offset = $offset }

    $records = @($result.data)
    $count += $records.Count

    if ($records.Count -lt $PageSize) {
      break
    }

    $offset += $PageSize
  }

  return $count
}

$rows = @()

if ($Workspace -in @("source", "both")) {
  if ([string]::IsNullOrWhiteSpace($SourceApiKey)) {
    throw "Missing SOURCE_ATTIO_API_KEY."
  }

  foreach ($object in $Objects) {
    $rows += [pscustomobject]@{
      workspace = "source"
      object    = $object
      count     = Get-Count -ApiKey $SourceApiKey -Object $object
    }
  }
}

if ($Workspace -in @("dev", "both")) {
  if ([string]::IsNullOrWhiteSpace($DevApiKey)) {
    throw "Missing DEV_ATTIO_API_KEY."
  }

  foreach ($object in $Objects) {
    $rows += [pscustomobject]@{
      workspace = "dev"
      object    = $object
      count     = Get-Count -ApiKey $DevApiKey -Object $object
    }
  }
}

$rows | Format-Table -AutoSize
