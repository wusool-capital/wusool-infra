param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [string]$DevApiKey = $env:DEV_ATTIO_API_KEY,
  [ValidateSet("source", "dev", "both")]
  [string]$Workspace = "both",
  [string]$OutputPath = (Join-Path (Resolve-Path ".").Path "outputs\attio")
)

$ErrorActionPreference = "Stop"

function Assert-Value {
  param(
    [string]$Value,
    [string]$Name
  )

  if ([string]::IsNullOrWhiteSpace($Value)) {
    throw "Missing $Name. Set it as an environment variable or pass it as a parameter."
  }
}

function Invoke-AttioGet {
  param(
    [string]$ApiKey,
    [string]$Path
  )

  $headers = @{
    Authorization = "Bearer $ApiKey"
    Accept        = "application/json"
  }

  Invoke-RestMethod -Method Get -Uri "https://api.attio.com/v2$Path" -Headers $headers
}

function Get-Items {
  param([object]$Response)

  if ($null -eq $Response.data) {
    return @()
  }

  return @($Response.data)
}

function Save-Json {
  param(
    [object]$Data,
    [string]$Path
  )

  $Data | ConvertTo-Json -Depth 100 | Set-Content -Path $Path -Encoding utf8
  Write-Host "Wrote $Path"
}

New-Item -ItemType Directory -Path $OutputPath -Force | Out-Null

if ($Workspace -in @("source", "both")) {
  Assert-Value -Value $SourceApiKey -Name "SOURCE_ATTIO_API_KEY"

  $sourceObjects = Invoke-AttioGet -ApiKey $SourceApiKey -Path "/objects"
  $sourceLists = Invoke-AttioGet -ApiKey $SourceApiKey -Path "/lists"
  $sourceObjectAttributes = @{}
  $sourceListAttributes = @{}

  foreach ($object in (Get-Items -Response $sourceObjects)) {
    $sourceObjectAttributes[$object.api_slug] = Invoke-AttioGet -ApiKey $SourceApiKey -Path "/objects/$($object.api_slug)/attributes"
  }

  foreach ($list in (Get-Items -Response $sourceLists)) {
    $sourceListAttributes[$list.api_slug] = Invoke-AttioGet -ApiKey $SourceApiKey -Path "/lists/$($list.api_slug)/attributes"
  }

  Save-Json -Data $sourceObjects -Path (Join-Path $OutputPath "source-objects.json")
  Save-Json -Data $sourceLists -Path (Join-Path $OutputPath "source-lists.json")
  Save-Json -Data $sourceObjectAttributes -Path (Join-Path $OutputPath "source-object-attributes.json")
  Save-Json -Data $sourceListAttributes -Path (Join-Path $OutputPath "source-list-attributes.json")
}

if ($Workspace -in @("dev", "both")) {
  Assert-Value -Value $DevApiKey -Name "DEV_ATTIO_API_KEY"

  $devObjects = Invoke-AttioGet -ApiKey $DevApiKey -Path "/objects"
  $devLists = Invoke-AttioGet -ApiKey $DevApiKey -Path "/lists"
  $devObjectAttributes = @{}
  $devListAttributes = @{}

  foreach ($object in (Get-Items -Response $devObjects)) {
    $devObjectAttributes[$object.api_slug] = Invoke-AttioGet -ApiKey $DevApiKey -Path "/objects/$($object.api_slug)/attributes"
  }

  foreach ($list in (Get-Items -Response $devLists)) {
    $devListAttributes[$list.api_slug] = Invoke-AttioGet -ApiKey $DevApiKey -Path "/lists/$($list.api_slug)/attributes"
  }

  Save-Json -Data $devObjects -Path (Join-Path $OutputPath "dev-objects.json")
  Save-Json -Data $devLists -Path (Join-Path $OutputPath "dev-lists.json")
  Save-Json -Data $devObjectAttributes -Path (Join-Path $OutputPath "dev-object-attributes.json")
  Save-Json -Data $devListAttributes -Path (Join-Path $OutputPath "dev-list-attributes.json")
}

Write-Host "Attio discovery complete."
