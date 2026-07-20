param(
  [string]$InputPath = (Join-Path (Resolve-Path ".").Path "outputs\attio"),
  [string]$ReportPath = (Join-Path (Resolve-Path ".").Path "outputs\attio\schema-comparison.md")
)

$ErrorActionPreference = "Stop"

function Read-Json {
  param([string]$Path)
  Get-Content -Raw -Path $Path | ConvertFrom-Json
}

function Get-AttributeSummary {
  param([object]$AttributeMap)

  $result = @{}
  foreach ($prop in $AttributeMap.PSObject.Properties) {
    $result[$prop.Name] = @($prop.Value.data) |
      Where-Object { -not $_.is_archived } |
      ForEach-Object {
        [pscustomobject]@{
          slug     = $_.api_slug
          title    = $_.title
          type     = $_.type
          writable = $_.is_writable
          system   = $_.is_system_attribute
        }
      }
  }
  return $result
}

function Add-Line {
  param(
    [System.Collections.Generic.List[string]]$Lines,
    [string]$Value = ""
  )
  $Lines.Add($Value) | Out-Null
}

$sourceObjects = Read-Json (Join-Path $InputPath "source-objects.json")
$sourceLists = Read-Json (Join-Path $InputPath "source-lists.json")
$devObjects = Read-Json (Join-Path $InputPath "dev-objects.json")
$devLists = Read-Json (Join-Path $InputPath "dev-lists.json")
$sourceObjectAttrs = Get-AttributeSummary (Read-Json (Join-Path $InputPath "source-object-attributes.json"))
$sourceListAttrs = Get-AttributeSummary (Read-Json (Join-Path $InputPath "source-list-attributes.json"))
$devObjectAttrs = Get-AttributeSummary (Read-Json (Join-Path $InputPath "dev-object-attributes.json"))
$devListAttrs = Get-AttributeSummary (Read-Json (Join-Path $InputPath "dev-list-attributes.json"))

$sourceObjectSlugs = @($sourceObjects.data.api_slug | Sort-Object)
$devObjectSlugs = @($devObjects.data.api_slug | Sort-Object)
$sourceListSlugs = @($sourceLists.data.api_slug | Sort-Object)
$devListSlugs = @($devLists.data.api_slug | Sort-Object)

$lines = [System.Collections.Generic.List[string]]::new()
Add-Line $lines "# Attio Schema Comparison"
Add-Line $lines
Add-Line $lines "## Objects"
Add-Line $lines
Add-Line $lines "| Source Object | In DEV | Missing DEV Writable Fields |"
Add-Line $lines "| --- | --- | --- |"

foreach ($slug in $sourceObjectSlugs) {
  $inDev = $devObjectSlugs -contains $slug
  $missing = @()
  if ($inDev -and $sourceObjectAttrs.ContainsKey($slug) -and $devObjectAttrs.ContainsKey($slug)) {
    $devAttrSlugs = @($devObjectAttrs[$slug].slug)
    $missing = @($sourceObjectAttrs[$slug] |
      Where-Object { $_.writable -and -not $_.system -and ($devAttrSlugs -notcontains $_.slug) } |
      ForEach-Object { $_.slug } |
      Sort-Object)
  }
  Add-Line $lines "| ``$slug`` | $inDev | $($missing -join ', ') |"
}

Add-Line $lines
Add-Line $lines "## Lists"
Add-Line $lines
Add-Line $lines "| Source List | Name | Parent Object | In DEV | Missing DEV Writable Fields |"
Add-Line $lines "| --- | --- | --- | --- | --- |"

foreach ($list in @($sourceLists.data | Sort-Object api_slug)) {
  $slug = $list.api_slug
  $inDev = $devListSlugs -contains $slug
  $missing = @()
  if ($inDev -and $sourceListAttrs.ContainsKey($slug) -and $devListAttrs.ContainsKey($slug)) {
    $devAttrSlugs = @($devListAttrs[$slug].slug)
    $missing = @($sourceListAttrs[$slug] |
      Where-Object { $_.writable -and -not $_.system -and ($devAttrSlugs -notcontains $_.slug) } |
      ForEach-Object { $_.slug } |
      Sort-Object)
  } elseif (-not $inDev -and $sourceListAttrs.ContainsKey($slug)) {
    $missing = @($sourceListAttrs[$slug] |
      Where-Object { $_.writable -and -not $_.system } |
      ForEach-Object { $_.slug } |
      Sort-Object)
  }

  Add-Line $lines "| ``$slug`` | $($list.name) | $($list.parent_object -join ', ') | $inDev | $($missing -join ', ') |"
}

New-Item -ItemType Directory -Path (Split-Path $ReportPath) -Force | Out-Null
$lines | Set-Content -Path $ReportPath -Encoding utf8
Write-Host "Wrote $ReportPath"
