param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [string]$DevApiKey = $env:DEV_ATTIO_API_KEY,
  [ValidateSet("source", "dev", "both")]
  [string]$Workspace = "both",
  [string[]]$Lists = @("buyer_brain", "valuation_tool_leads", "buy_side_mandates"),
  [int]$PageSize = 500
)

$ErrorActionPreference = "Stop"

function New-Headers {
  param([string]$ApiKey)

  @{
    Authorization  = "Bearer $ApiKey"
    Accept         = "application/json"
    "Content-Type" = "application/json"
  }
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

function Count-ListEntries {
  param(
    [hashtable]$Headers,
    [string]$List
  )

  $count = 0
  $offset = 0

  while ($true) {
    $result = Invoke-AttioPost `
      -Headers $Headers `
      -Path "/lists/$List/entries/query" `
      -Body @{ limit = $PageSize; offset = $offset }

    $entries = @($result.data)
    $count += $entries.Count

    if ($entries.Count -lt $PageSize) {
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

  $headers = New-Headers -ApiKey $SourceApiKey
  foreach ($list in $Lists) {
    $rows += [pscustomobject]@{
      workspace = "source"
      list      = $list
      count     = Count-ListEntries -Headers $headers -List $list
    }
  }
}

if ($Workspace -in @("dev", "both")) {
  if ([string]::IsNullOrWhiteSpace($DevApiKey)) {
    throw "Missing DEV_ATTIO_API_KEY."
  }

  $headers = New-Headers -ApiKey $DevApiKey
  foreach ($list in $Lists) {
    $rows += [pscustomobject]@{
      workspace = "dev"
      list      = $list
      count     = Count-ListEntries -Headers $headers -List $list
    }
  }
}

$rows | Format-Table -AutoSize
