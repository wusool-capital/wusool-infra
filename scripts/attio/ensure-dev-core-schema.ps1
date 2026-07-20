param(
  [string]$DevApiKey = $env:DEV_ATTIO_API_KEY,
  [string]$InputPath = (Join-Path (Resolve-Path ".").Path "outputs\attio"),
  [string[]]$Objects = @("companies", "people", "deals"),
  [string[]]$Lists = @("buyer_brain", "valuation_tool_leads", "buy_side_mandates")
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

function Read-Json {
  param([string]$Path)
  Get-Content -Raw -Path $Path | ConvertFrom-Json
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

function Get-AttrsBySlug {
  param([object]$AttributeResponse)

  $result = @{}
  foreach ($attr in @($AttributeResponse.data)) {
    if (-not $attr.is_archived) {
      $result[$attr.api_slug] = $attr
    }
  }
  return $result
}

function New-AttributeBody {
  param([object]$SourceAttribute)

  $data = @{
    title          = $SourceAttribute.title
    description    = if ($null -eq $SourceAttribute.description) { "" } else { $SourceAttribute.description }
    api_slug       = $SourceAttribute.api_slug
    type           = $SourceAttribute.type
    is_required    = $false
    is_unique      = $false
    is_multiselect = [bool]$SourceAttribute.is_multiselect
    config         = @{}
  }

  if ($SourceAttribute.type -eq "currency" -and $SourceAttribute.config.currency.default_currency_code) {
    $data.config = @{
      currency = @{
        default_currency_code = $SourceAttribute.config.currency.default_currency_code
        display_type          = $SourceAttribute.config.currency.display_type
      }
    }
  }

  return @{ data = $data }
}

function Ensure-Attribute {
  param(
    [string]$Target,
    [string]$Identifier,
    [object]$SourceAttribute,
    [hashtable]$DevAttrs
  )

  $slug = $SourceAttribute.api_slug

  if ($DevAttrs.ContainsKey($slug)) {
    Write-Host "$Target/$Identifier attribute exists: $slug"
    return
  }

  if (-not $SourceAttribute.is_writable -or $SourceAttribute.is_system_attribute) {
    return
  }

  if ($SourceAttribute.type -in @("record-reference", "actor-reference", "interaction")) {
    Write-Warning "Skipping $Target/$Identifier $slug because relationship/actor/interaction attributes need explicit review."
    return
  }

  try {
    Invoke-AttioPost -Path "/$Target/$Identifier/attributes" -Body (New-AttributeBody -SourceAttribute $SourceAttribute) | Out-Null
    Write-Host "Created $Target/$Identifier attribute: $slug"
  } catch {
    $errorBody = $_.ErrorDetails.Message
    if ($errorBody -match "slug_conflict") {
      Write-Host "$Target/$Identifier attribute exists: $slug"
      return
    }
    Write-Warning "Failed to create $Target/$Identifier attribute $slug. $errorBody"
  }
}

$sourceLists = Read-Json (Join-Path $InputPath "source-lists.json")
$devLists = Read-Json (Join-Path $InputPath "dev-lists.json")
$sourceObjectAttrs = Read-Json (Join-Path $InputPath "source-object-attributes.json")
$sourceListAttrs = Read-Json (Join-Path $InputPath "source-list-attributes.json")
$devObjectAttrs = Read-Json (Join-Path $InputPath "dev-object-attributes.json")
$devListAttrs = Read-Json (Join-Path $InputPath "dev-list-attributes.json")

foreach ($object in $Objects) {
  Write-Host "Ensuring object attributes for $object"
  $sourceAttrs = Get-AttrsBySlug $sourceObjectAttrs.$object
  $devAttrs = Get-AttrsBySlug $devObjectAttrs.$object

  foreach ($attr in $sourceAttrs.Values) {
    Ensure-Attribute -Target "objects" -Identifier $object -SourceAttribute $attr -DevAttrs $devAttrs
  }
}

$devListSlugs = @($devLists.data.api_slug)

foreach ($listSlug in $Lists) {
  $sourceList = @($sourceLists.data) | Where-Object { $_.api_slug -eq $listSlug } | Select-Object -First 1
  if ($null -eq $sourceList) {
    Write-Warning "Source list not found: $listSlug"
    continue
  }

  if ($devListSlugs -notcontains $listSlug) {
    $parentObject = @($sourceList.parent_object)[0]
    $body = @{
      data = @{
        name                    = $sourceList.name
        api_slug                = $sourceList.api_slug
        parent_object           = $parentObject
        workspace_access        = "full-access"
        workspace_member_access = @()
      }
    }

    try {
      Invoke-AttioPost -Path "/lists" -Body $body | Out-Null
      Write-Host "Created list: $listSlug"
    } catch {
      $errorBody = $_.ErrorDetails.Message
      if ($errorBody -match "slug_conflict") {
        Write-Host "List exists: $listSlug"
      } else {
        Write-Warning "Failed to create list $listSlug. $errorBody"
        continue
      }
    }
  } else {
    Write-Host "List exists: $listSlug"
  }

  $currentListAttrs = Invoke-AttioGet -Path "/lists/$listSlug/attributes"
  $devAttrs = Get-AttrsBySlug $currentListAttrs
  $sourceAttrs = Get-AttrsBySlug $sourceListAttrs.$listSlug

  foreach ($attr in $sourceAttrs.Values) {
    Ensure-Attribute -Target "lists" -Identifier $listSlug -SourceAttribute $attr -DevAttrs $devAttrs
  }
}

Write-Host "DEV core schema ensure complete. Re-run discovery and comparison next."
