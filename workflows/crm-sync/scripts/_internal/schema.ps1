param(
 [ValidateSet("organizations","person","deals","buyer_role","seller_role")][string]$Entity,
 [string]$SourceApiKey=$env:SOURCE_ATTIO_API_KEY,[string]$DevApiKey=$env:DEV_ATTIO_API_KEY,
 [switch]$FailOnDrift,[switch]$Apply
)
$ErrorActionPreference="Stop"
function Invoke-OrganizationSchema {
param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [string]$DevApiKey = $env:DEV_ATTIO_API_KEY,
  [switch]$Apply
)


# Reusable Attio custom Organization schema reconciliation.
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($SourceApiKey)) {
  throw "Missing SOURCE_ATTIO_API_KEY."
}
if ([string]::IsNullOrWhiteSpace($DevApiKey)) {
  throw "Missing DEV_ATTIO_API_KEY."
}

$sourceHeaders = @{
  Authorization = "Bearer $($SourceApiKey.Trim())"
  Accept = "application/json"
  "Content-Type" = "application/json"
}
$devHeaders = @{
  Authorization = "Bearer $($DevApiKey.Trim())"
  Accept = "application/json"
  "Content-Type" = "application/json"
}

$decisionsPath = Join-Path $PSScriptRoot "..\config\migration-decisions.json"
$decisions = Get-Content $decisionsPath -Raw | ConvertFrom-Json
$expectedWorkspaceId = [string]$decisions.dev_workspace_id

function Invoke-AttioRequest {
  param(
    [ValidateSet("Get", "Post", "Patch")]
    [string]$Method,
    [hashtable]$Headers,
    [string]$Path,
    [object]$Body
  )

  $parameters = @{
    Method = $Method
    Uri = "https://api.attio.com/v2$Path"
    Headers = $Headers
  }
  if ($null -ne $Body) {
    $parameters.Body = [System.Text.Encoding]::UTF8.GetBytes(
      ($Body | ConvertTo-Json -Depth 30)
    )
  }
  Invoke-RestMethod @parameters
}

function Get-Attributes {
  param(
    [hashtable]$Headers,
    [string]$ObjectSlug,
    [switch]$IncludeArchived
  )

  $suffix = if ($IncludeArchived) { "?show_archived=true" } else { "" }
  $response = Invoke-AttioRequest -Method Get -Headers $Headers `
    -Path "/objects/$ObjectSlug/attributes$suffix"
  $map = @{}
  foreach ($attribute in @($response.data)) {
    $map[[string]$attribute.api_slug] = $attribute
  }
  return $map
}

function Get-OptionTitles {
  param(
    [hashtable]$Headers,
    [string]$ObjectSlug,
    [string]$AttributeSlug,
    [switch]$IncludeArchived
  )

  $response = Invoke-AttioRequest -Method Get -Headers $Headers `
    -Path "/objects/$ObjectSlug/attributes/$AttributeSlug/options"
  return @(
    $response.data |
      Where-Object { ($IncludeArchived -or -not $_.is_archived) -and $_.title } |
      ForEach-Object { [string]$_.title }
  )
}

$targetObject = Invoke-AttioRequest -Method Get -Headers $devHeaders `
  -Path "/objects/organizations"
$connectedWorkspaceId = [string]$targetObject.data.id.workspace_id

if ($connectedWorkspaceId -ne $expectedWorkspaceId) {
  throw "DEV workspace mismatch. Expected $expectedWorkspaceId but connected to $connectedWorkspaceId."
}
if ($targetObject.data.api_slug -ne "organizations") {
  throw "The DEV custom object slug is not organizations."
}

$fields = @(
  [pscustomobject]@{ Title = "Name"; Slug = "name"; Type = "text"; Multi = $false; Required = $true; Unique = $false; SourceOption = $null },
  [pscustomobject]@{ Title = "Description"; Slug = "description"; Type = "text"; Multi = $false; Required = $false; Unique = $false; SourceOption = $null },
  [pscustomobject]@{ Title = "Type"; Slug = "type"; Type = "select"; Multi = $true; Required = $false; Unique = $false; SourceOption = "type" },
  [pscustomobject]@{ Title = "Client Type"; Slug = "client_type"; Type = "select"; Multi = $false; Required = $false; Unique = $false; SourceOption = "client_type" },
  [pscustomobject]@{ Title = "Sector Focus"; Slug = "sector_focus"; Type = "select"; Multi = $true; Required = $false; Unique = $false; SourceOption = "sector_focus" },
  [pscustomobject]@{ Title = "Stage Focus"; Slug = "stage_focus"; Type = "select"; Multi = $true; Required = $false; Unique = $false; SourceOption = "stage" },
  [pscustomobject]@{ Title = "Geographic Focus"; Slug = "geographic_focus"; Type = "select"; Multi = $true; Required = $false; Unique = $false; SourceOption = "geographic_focus" },
  [pscustomobject]@{ Title = "HQ Country"; Slug = "hq_country"; Type = "text"; Multi = $false; Required = $false; Unique = $false; SourceOption = $null },
  [pscustomobject]@{ Title = "Domains"; Slug = "domains"; Type = "text"; Multi = $false; Required = $false; Unique = $false; SourceOption = $null },
  [pscustomobject]@{ Title = "Logo URL"; Slug = "logo_url"; Type = "text"; Multi = $false; Required = $false; Unique = $false; SourceOption = $null },
  [pscustomobject]@{ Title = "Categories"; Slug = "categories"; Type = "select"; Multi = $true; Required = $false; Unique = $false; SourceOption = "categories" },
  [pscustomobject]@{ Title = "Relationship Status"; Slug = "relationship_status"; Type = "select"; Multi = $false; Required = $false; Unique = $false; SourceOption = $null },
  [pscustomobject]@{ Title = "Connection Strength"; Slug = "connection_strength"; Type = "select"; Multi = $false; Required = $false; Unique = $false; SourceOption = "strongest_connection_strength" },
  [pscustomobject]@{ Title = "Owner"; Slug = "owner"; Type = "actor-reference"; Multi = $false; Required = $false; Unique = $false; SourceOption = $null },
  [pscustomobject]@{ Title = "Last Interaction At"; Slug = "last_interaction_at"; Type = "timestamp"; Multi = $false; Required = $false; Unique = $false; SourceOption = $null },
  [pscustomobject]@{ Title = "Legacy Attio ID"; Slug = "legacy_attio_id"; Type = "text"; Multi = $false; Required = $false; Unique = $true; SourceOption = $null },
  [pscustomobject]@{ Title = "Funding Raised"; Slug = "funding_raised"; Type = "currency"; Multi = $false; Required = $false; Unique = $false; SourceOption = $null; Config = @{ currency = @{ default_currency_code = "USD"; display_type = "symbol" } } },
  [pscustomobject]@{ Title = "Estimated ARR"; Slug = "estimated_arr"; Type = "select"; Multi = $false; Required = $false; Unique = $false; SourceOption = $null; FixedOptions = @('$0-$1M', '$1M-$10M', '$10M-$50M', '$50M-$100M', '$100M-$250M', '$250M-$500M', '$500M-$1B', '$1B-$10B', '$10B+') },
  [pscustomobject]@{ Title = "Is Active"; Slug = "is_active"; Type = "checkbox"; Multi = $false; Required = $false; Unique = $false; SourceOption = $null; Config = @{} },
  # Created directly via the API when first migrated (2026-08-19), never
  # tracked here until now -- added 2026-08-23 so drift/deletion gets caught
  # like every other field instead of silently trusted (same gap fixed for
  # Person the same day).
  [pscustomobject]@{ Title = "LinkedIn"; Slug = "linkedin"; Type = "text"; Multi = $false; Required = $false; Unique = $false; SourceOption = $null },
  [pscustomobject]@{ Title = "AngelList"; Slug = "angellist"; Type = "text"; Multi = $false; Required = $false; Unique = $false; SourceOption = $null },
  [pscustomobject]@{ Title = "Facebook"; Slug = "facebook"; Type = "text"; Multi = $false; Required = $false; Unique = $false; SourceOption = $null },
  [pscustomobject]@{ Title = "Instagram"; Slug = "instagram"; Type = "text"; Multi = $false; Required = $false; Unique = $false; SourceOption = $null },
  [pscustomobject]@{ Title = "Twitter"; Slug = "twitter"; Type = "text"; Multi = $false; Required = $false; Unique = $false; SourceOption = $null },
  [pscustomobject]@{ Title = "Twitter Follower Count"; Slug = "twitter_follower_count"; Type = "number"; Multi = $false; Required = $false; Unique = $false; SourceOption = $null },
  [pscustomobject]@{ Title = "Foundation Date"; Slug = "foundation_date"; Type = "date"; Multi = $false; Required = $false; Unique = $false; SourceOption = $null },
  [pscustomobject]@{ Title = "Ticket Size"; Slug = "ticket_size"; Type = "text"; Multi = $false; Required = $false; Unique = $false; SourceOption = $null },
  [pscustomobject]@{ Title = "Employee Range"; Slug = "employee_range"; Type = "select"; Multi = $false; Required = $false; Unique = $false; SourceOption = "employee_range" }
)

$targetAttributes = Get-Attributes -Headers $devHeaders -ObjectSlug "organizations"
$allTargetAttributes = Get-Attributes -Headers $devHeaders -ObjectSlug "organizations" -IncludeArchived
$actions = @()

foreach ($field in $fields) {
  if ($targetAttributes.ContainsKey($field.Slug)) {
    $current = $targetAttributes[$field.Slug]
    if ($current.type -ne $field.Type -or
        [bool]$current.is_multiselect -ne [bool]$field.Multi) {
      if ($field.Slug -ne "relationship_status" -or
          $current.type -ne "select" -or
          [bool]$current.is_multiselect -ne $true -or
          [bool]$field.Multi -ne $false) {
        throw "DEV organizations/$($field.Slug) exists with type=$($current.type), multiselect=$($current.is_multiselect); expected type=$($field.Type), multiselect=$($field.Multi)."
      }

      $currentId = [string]$current.id.attribute_id
      $legacySlug = "relationship_status_legacy_$($currentId.Substring(0, 8))"
      $actions += "archive_multiselect_attribute:relationship_status:$legacySlug"
      if (-not $Apply) {
        Write-Host "DRY RUN: would archive and rename active relationship_status -> $legacySlug."
      } else {
        Invoke-AttioRequest -Method Patch -Headers $devHeaders `
          -Path "/objects/organizations/attributes/$currentId" `
          -Body @{ data = @{
            title = "Relationship Status (Legacy Multi Select)"
            api_slug = $legacySlug
            is_archived = $true
          } } | Out-Null
        Write-Host "ARCHIVED: relationship_status -> $legacySlug"
      }
      $targetAttributes.Remove($field.Slug)
      $allTargetAttributes.Remove($field.Slug)
    } else {
      Write-Host "EXISTS: $($field.Slug)"
      continue
    }
  }

  # Attio keeps deleted attributes archived and continues reserving their API
  # slugs. Move an archived predecessor out of the way before recreating a
  # field with corrected cardinality (for example enum -> enum[]).
  if ($allTargetAttributes.ContainsKey($field.Slug)) {
    $archived = $allTargetAttributes[$field.Slug]
    $archivedId = [string]$archived.id.attribute_id
    $legacySlug = "$($field.Slug)_legacy_$($archivedId.Substring(0, 8))"
    $actions += "rename_archived_attribute:$($field.Slug):$legacySlug"
    if (-not $Apply) {
      Write-Host "DRY RUN: would rename archived $($field.Slug) -> $legacySlug."
    } else {
      Invoke-AttioRequest -Method Patch -Headers $devHeaders `
        -Path "/objects/organizations/attributes/$($archived.id.attribute_id)" `
        -Body @{ data = @{
          title = "$($field.Title) (Legacy Single Select)"
          api_slug = $legacySlug
          is_archived = $true
        } } | Out-Null
      Write-Host "RENAMED ARCHIVED: $($field.Slug) -> $legacySlug"
    }
  }

  $actions += "create_attribute:$($field.Slug)"
  if (-not $Apply) {
    Write-Host "DRY RUN: would create $($field.Slug) ($($field.Type), multiselect=$($field.Multi))."
    continue
  }

  $body = @{
    data = @{
      title = $field.Title
      description = "Wusool target schema field."
      api_slug = $field.Slug
      type = $field.Type
      is_required = [bool]$field.Required
      is_unique = [bool]$field.Unique
      is_multiselect = [bool]$field.Multi
      config = if ($field.Config) { $field.Config } else { @{} }
    }
  }
  Invoke-AttioRequest -Method Post -Headers $devHeaders `
    -Path "/objects/organizations/attributes" -Body $body | Out-Null
  Write-Host "CREATED: $($field.Slug)"
}

if ($Apply) {
  $targetAttributes = Get-Attributes -Headers $devHeaders -ObjectSlug "organizations"
}

foreach ($field in @($fields | Where-Object SourceOption)) {
  if (-not $Apply -and -not $targetAttributes.ContainsKey($field.Slug)) {
    Write-Host "DRY RUN: would copy options $($field.SourceOption) -> $($field.Slug)."
    continue
  }

  $sourceTitles = @(
    Get-OptionTitles -Headers $sourceHeaders -ObjectSlug "companies" `
      -AttributeSlug $field.SourceOption -IncludeArchived
  )
  $targetTitles = @(
    Get-OptionTitles -Headers $devHeaders -ObjectSlug "organizations" `
      -AttributeSlug $field.Slug
  )
  $existing = @{}
  foreach ($title in $targetTitles) {
    $existing[$title.Trim().ToLowerInvariant()] = $true
  }

  foreach ($title in $sourceTitles) {
    $key = $title.Trim().ToLowerInvariant()
    if ($existing.ContainsKey($key)) { continue }
    $actions += "create_option:$($field.Slug):$title"
    if (-not $Apply) {
      Write-Host "DRY RUN: would create $($field.Slug) option '$title'."
      continue
    }
    Invoke-AttioRequest -Method Post -Headers $devHeaders `
      -Path "/objects/organizations/attributes/$($field.Slug)/options" `
      -Body @{ data = @{ title = $title } } | Out-Null
    $existing[$key] = $true
    Write-Host "CREATED OPTION: $($field.Slug) -> $title"
  }
}

foreach ($field in @($fields | Where-Object FixedOptions)) {
  if (-not $Apply -and -not $targetAttributes.ContainsKey($field.Slug)) {
    foreach ($title in $field.FixedOptions) {
      $actions += "create_option:$($field.Slug):$title"
      Write-Host "DRY RUN: would create $($field.Slug) option '$title'."
    }
    continue
  }

  $targetTitles = @(
    Get-OptionTitles -Headers $devHeaders -ObjectSlug "organizations" `
      -AttributeSlug $field.Slug
  )
  $existing = @{}
  foreach ($title in $targetTitles) {
    $existing[$title.Trim().ToLowerInvariant()] = $true
  }

  foreach ($title in $field.FixedOptions) {
    $key = $title.Trim().ToLowerInvariant()
    if ($existing.ContainsKey($key)) { continue }
    $actions += "create_option:$($field.Slug):$title"
    if (-not $Apply) {
      Write-Host "DRY RUN: would create $($field.Slug) option '$title'."
      continue
    }
    Invoke-AttioRequest -Method Post -Headers $devHeaders `
      -Path "/objects/organizations/attributes/$($field.Slug)/options" `
      -Body @{ data = @{ title = $title } } | Out-Null
    $existing[$key] = $true
    Write-Host "CREATED OPTION: $($field.Slug) -> $title"
  }
}

$relationshipField = $fields | Where-Object Slug -eq "relationship_status"
if (-not $Apply -and -not $targetAttributes.ContainsKey("relationship_status")) {
  foreach ($title in @("Warm", "Cold", "Closed")) {
    Write-Host "DRY RUN: would create relationship_status option '$title'."
    $actions += "create_option:relationship_status:$title"
  }
} else {
  $targetTitles = @(Get-OptionTitles -Headers $devHeaders -ObjectSlug "organizations" `
    -AttributeSlug "relationship_status")
  $existing = @{}
  foreach ($title in $targetTitles) { $existing[$title.Trim().ToLowerInvariant()] = $true }
  foreach ($title in @("Warm", "Cold", "Closed")) {
    $key = $title.ToLowerInvariant()
    if ($existing.ContainsKey($key)) { continue }
    $actions += "create_option:relationship_status:$title"
    if (-not $Apply) {
      Write-Host "DRY RUN: would create relationship_status option '$title'."
      continue
    }
    Invoke-AttioRequest -Method Post -Headers $devHeaders `
      -Path "/objects/organizations/attributes/relationship_status/options" `
      -Body @{ data = @{ title = $title } } | Out-Null
    Write-Host "CREATED OPTION: relationship_status -> $title"
  }
}

Write-Host ""
if ($Apply) {
  Write-Host "Organization schema apply complete."
} else {
  Write-Host "Organization schema dry run complete. Planned actions: $($actions.Count). Add -Apply to create them."
}

}
function Invoke-PersonSchema {
param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [string]$DevApiKey = $env:DEV_ATTIO_API_KEY,
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
  Authorization = "Bearer $($SourceApiKey.Trim())"
  Accept = "application/json"
  "Content-Type" = "application/json"
}
$devHeaders = @{
  Authorization = "Bearer $($DevApiKey.Trim())"
  Accept = "application/json"
  "Content-Type" = "application/json"
}

function Invoke-AttioRequest {
  param(
    [ValidateSet("Get", "Post", "Patch")]
    [string]$Method,
    [hashtable]$Headers,
    [string]$Path,
    [object]$Body
  )

  $parameters = @{
    Method = $Method
    Uri = "https://api.attio.com/v2$Path"
    Headers = $Headers
  }
  if ($null -ne $Body) {
    $parameters.Body = [System.Text.Encoding]::UTF8.GetBytes(
      ($Body | ConvertTo-Json -Depth 30)
    )
  }
  Invoke-RestMethod @parameters
}

function Get-Attributes {
  param(
    [hashtable]$Headers,
    [string]$ObjectSlug,
    [switch]$IncludeArchived
  )

  $suffix = if ($IncludeArchived) { "?show_archived=true" } else { "" }
  $response = Invoke-AttioRequest -Method Get -Headers $Headers `
    -Path "/objects/$ObjectSlug/attributes$suffix"
  $map = @{}
  foreach ($attribute in @($response.data)) {
    $map[[string]$attribute.api_slug] = $attribute
  }
  return $map
}

function Get-OptionTitles {
  param(
    [hashtable]$Headers,
    [string]$ObjectSlug,
    [string]$AttributeSlug
  )

  $response = Invoke-AttioRequest -Method Get -Headers $Headers `
    -Path "/objects/$ObjectSlug/attributes/$AttributeSlug/options"
  return @(
    $response.data |
      Where-Object { -not $_.is_archived -and $_.title } |
      ForEach-Object { [string]$_.title }
  )
}

$decisionsPath = Join-Path $PSScriptRoot "..\config\migration-decisions.json"
$decisions = Get-Content $decisionsPath -Raw | ConvertFrom-Json
$expectedWorkspaceId = [string]$decisions.dev_workspace_id

$targetObject = Invoke-AttioRequest -Method Get -Headers $devHeaders `
  -Path "/objects/person"
if ([string]$targetObject.data.id.workspace_id -ne $expectedWorkspaceId) {
  throw "DEV workspace mismatch."
}
if ([string]$targetObject.data.api_slug -ne "person") {
  throw "The DEV custom object slug must be person."
}

$fields = @(
  [pscustomobject]@{ Title = "Name"; Slug = "name"; Type = "text"; Multi = $false; Required = $true; Unique = $false; SourceOption = $null; AllowedObject = $null },
  [pscustomobject]@{ Title = "Role"; Slug = "role"; Type = "select"; Multi = $true; Required = $false; Unique = $false; SourceOption = "role"; AllowedObject = $null },
  [pscustomobject]@{ Title = "Company"; Slug = "company"; Type = "record-reference"; Multi = $false; Required = $false; Unique = $false; SourceOption = $null; AllowedObject = "organizations" },
  # Attio does not support creating email-address attributes on custom objects.
  # Multiple SOURCE emails are stored as comma-delimited text during migration.
  [pscustomobject]@{ Title = "Email"; Slug = "email"; Type = "text"; Multi = $false; Required = $false; Unique = $false; SourceOption = $null; AllowedObject = $null },
  [pscustomobject]@{ Title = "LinkedIn"; Slug = "linkedin"; Type = "text"; Multi = $false; Required = $false; Unique = $false; SourceOption = $null; AllowedObject = $null },
  [pscustomobject]@{ Title = "Relationship Status"; Slug = "relationship_status"; Type = "select"; Multi = $false; Required = $false; Unique = $false; SourceOption = $null; AllowedObject = $null },
  [pscustomobject]@{ Title = "Connection Strength"; Slug = "connection_strength"; Type = "select"; Multi = $false; Required = $false; Unique = $false; SourceOption = "strongest_connection_strength"; AllowedObject = $null },
  [pscustomobject]@{ Title = "Owner"; Slug = "owner"; Type = "actor-reference"; Multi = $false; Required = $false; Unique = $false; SourceOption = $null; AllowedObject = $null },
  [pscustomobject]@{ Title = "Last Interaction At"; Slug = "last_interaction_at"; Type = "timestamp"; Multi = $false; Required = $false; Unique = $false; SourceOption = $null; AllowedObject = $null },
  [pscustomobject]@{ Title = "Legacy Attio ID"; Slug = "legacy_attio_id"; Type = "text"; Multi = $false; Required = $false; Unique = $true; SourceOption = $null; AllowedObject = $null },
  # Created directly via the API when first migrated (2026-08-19), never
  # tracked here until now -- added 2026-08-23 so drift/deletion gets caught
  # like every other field instead of silently trusted.
  [pscustomobject]@{ Title = "Job Title"; Slug = "job_title"; Type = "text"; Multi = $false; Required = $false; Unique = $false; SourceOption = $null; AllowedObject = $null },
  [pscustomobject]@{ Title = "Contact Type"; Slug = "contact_type"; Type = "select"; Multi = $false; Required = $false; Unique = $false; SourceOption = "contact_type"; AllowedObject = $null },
  [pscustomobject]@{ Title = "Phone"; Slug = "phone"; Type = "text"; Multi = $false; Required = $false; Unique = $false; SourceOption = $null; AllowedObject = $null },
  [pscustomobject]@{ Title = "Avatar URL"; Slug = "avatar_url"; Type = "text"; Multi = $false; Required = $false; Unique = $false; SourceOption = $null; AllowedObject = $null },
  [pscustomobject]@{ Title = "AngelList"; Slug = "angellist"; Type = "text"; Multi = $false; Required = $false; Unique = $false; SourceOption = $null; AllowedObject = $null },
  [pscustomobject]@{ Title = "Facebook"; Slug = "facebook"; Type = "text"; Multi = $false; Required = $false; Unique = $false; SourceOption = $null; AllowedObject = $null },
  [pscustomobject]@{ Title = "Instagram"; Slug = "instagram"; Type = "text"; Multi = $false; Required = $false; Unique = $false; SourceOption = $null; AllowedObject = $null },
  [pscustomobject]@{ Title = "Twitter"; Slug = "twitter"; Type = "text"; Multi = $false; Required = $false; Unique = $false; SourceOption = $null; AllowedObject = $null },
  [pscustomobject]@{ Title = "Twitter Follower Count"; Slug = "twitter_follower_count"; Type = "number"; Multi = $false; Required = $false; Unique = $false; SourceOption = $null; AllowedObject = $null }
)

$targetAttributes = Get-Attributes -Headers $devHeaders -ObjectSlug "person"
$allTargetAttributes = Get-Attributes -Headers $devHeaders -ObjectSlug "person" -IncludeArchived
$actions = @()

foreach ($field in $fields) {
  if ($targetAttributes.ContainsKey($field.Slug)) {
    $current = $targetAttributes[$field.Slug]
    if ([string]$current.type -ne $field.Type -or
        [bool]$current.is_multiselect -ne [bool]$field.Multi) {
      if ($field.Slug -ne "relationship_status" -or
          [string]$current.type -ne "select" -or
          [bool]$current.is_multiselect -ne $true -or
          [bool]$field.Multi -ne $false) {
        throw "DEV person/$($field.Slug) has type=$($current.type), multiselect=$($current.is_multiselect); expected type=$($field.Type), multiselect=$($field.Multi)."
      }

      $currentId = [string]$current.id.attribute_id
      $legacySlug = "relationship_status_legacy_$($currentId.Substring(0, 8))"
      $actions += "archive_multiselect_attribute:relationship_status:$legacySlug"
      if (-not $Apply) {
        Write-Host "DRY RUN: would archive and rename active relationship_status -> $legacySlug."
      } else {
        Invoke-AttioRequest -Method Patch -Headers $devHeaders `
          -Path "/objects/person/attributes/$currentId" `
          -Body @{ data = @{
            title = "Relationship Status (Legacy Multi Select)"
            api_slug = $legacySlug
            is_archived = $true
          } } | Out-Null
        Write-Host "ARCHIVED: relationship_status -> $legacySlug"
      }
      $targetAttributes.Remove($field.Slug)
      $allTargetAttributes.Remove($field.Slug)
    } else {
      Write-Host "EXISTS: $($field.Slug)"
      continue
    }
  }

  # Deleted attributes remain archived and reserve their API slug. Rename an
  # archived predecessor before recreating it with corrected cardinality.
  if ($allTargetAttributes.ContainsKey($field.Slug)) {
    $archived = $allTargetAttributes[$field.Slug]
    $archivedId = [string]$archived.id.attribute_id
    $legacySlug = "$($field.Slug)_legacy_$($archivedId.Substring(0, 8))"
    $actions += "rename_archived_attribute:$($field.Slug):$legacySlug"
    if (-not $Apply) {
      Write-Host "DRY RUN: would rename archived $($field.Slug) -> $legacySlug."
    } else {
      Invoke-AttioRequest -Method Patch -Headers $devHeaders `
        -Path "/objects/person/attributes/$archivedId" `
        -Body @{ data = @{
          title = "$($field.Title) (Legacy Single Select)"
          api_slug = $legacySlug
          is_archived = $true
        } } | Out-Null
      Write-Host "RENAMED ARCHIVED: $($field.Slug) -> $legacySlug"
    }
  }

  $actions += "create_attribute:$($field.Slug)"
  if (-not $Apply) {
    Write-Host "DRY RUN: would create $($field.Slug) ($($field.Type), multiselect=$($field.Multi))."
    continue
  }

  $data = @{
    title = $field.Title
    description = "Wusool target Person schema field."
    api_slug = $field.Slug
    type = $field.Type
    is_required = [bool]$field.Required
    is_unique = [bool]$field.Unique
    is_multiselect = [bool]$field.Multi
    config = @{}
  }
  if ($field.AllowedObject) {
    $data.config = @{
      record_reference = @{
        allowed_objects = @([string]$field.AllowedObject)
      }
    }
  }

  Invoke-AttioRequest -Method Post -Headers $devHeaders `
    -Path "/objects/person/attributes" -Body @{ data = $data } | Out-Null
  Write-Host "CREATED: $($field.Slug)"
}

if ($Apply) {
  $targetAttributes = Get-Attributes -Headers $devHeaders -ObjectSlug "person"
}

foreach ($field in @($fields | Where-Object SourceOption)) {
  if (-not $Apply -and -not $targetAttributes.ContainsKey($field.Slug)) {
    Write-Host "DRY RUN: would copy options $($field.SourceOption) -> $($field.Slug)."
    continue
  }

  $sourceTitles = @(Get-OptionTitles -Headers $sourceHeaders `
    -ObjectSlug "people" -AttributeSlug $field.SourceOption)
  $targetTitles = @(Get-OptionTitles -Headers $devHeaders `
    -ObjectSlug "person" -AttributeSlug $field.Slug)
  $existing = @{}
  foreach ($title in $targetTitles) {
    $existing[$title.Trim().ToLowerInvariant()] = $true
  }

  foreach ($title in $sourceTitles) {
    $key = $title.Trim().ToLowerInvariant()
    if ($existing.ContainsKey($key)) { continue }
    $actions += "create_option:$($field.Slug):$title"
    if (-not $Apply) {
      Write-Host "DRY RUN: would create $($field.Slug) option '$title'."
      continue
    }
    Invoke-AttioRequest -Method Post -Headers $devHeaders `
      -Path "/objects/person/attributes/$($field.Slug)/options" `
      -Body @{ data = @{ title = $title } } | Out-Null
    $existing[$key] = $true
    Write-Host "CREATED OPTION: $($field.Slug) -> $title"
  }
}

if (-not $Apply -and -not $targetAttributes.ContainsKey("relationship_status")) {
  foreach ($title in @("Warm", "Cold", "Closed")) {
    Write-Host "DRY RUN: would create relationship_status option '$title'."
    $actions += "create_option:relationship_status:$title"
  }
} else {
  $targetTitles = @(Get-OptionTitles -Headers $devHeaders `
    -ObjectSlug "person" -AttributeSlug "relationship_status")
  $existing = @{}
  foreach ($title in $targetTitles) { $existing[$title.Trim().ToLowerInvariant()] = $true }
  foreach ($title in @("Warm", "Cold", "Closed")) {
    $key = $title.ToLowerInvariant()
    if ($existing.ContainsKey($key)) { continue }
    $actions += "create_option:relationship_status:$title"
    if (-not $Apply) {
      Write-Host "DRY RUN: would create relationship_status option '$title'."
      continue
    }
    Invoke-AttioRequest -Method Post -Headers $devHeaders `
      -Path "/objects/person/attributes/relationship_status/options" `
      -Body @{ data = @{ title = $title } } | Out-Null
    Write-Host "CREATED OPTION: relationship_status -> $title"
  }
}

Write-Host ""
if ($Apply) {
  Write-Host "Person schema apply complete."
} else {
  Write-Host "Person schema dry run complete. Planned actions: $($actions.Count). Add -Apply to create them."
}

}
function Invoke-DealSchema {
param(
  [string]$DevApiKey=$env:DEV_ATTIO_API_KEY,
  [switch]$FailOnDrift,
  [switch]$Apply
)

$ErrorActionPreference="Stop"
if([string]::IsNullOrWhiteSpace($DevApiKey)){$DevApiKey=[Environment]::GetEnvironmentVariable("DEV_ATTIO_API_KEY","User")}
if([string]::IsNullOrWhiteSpace($DevApiKey)){throw "Missing DEV_ATTIO_API_KEY."}
$headers=@{Authorization="Bearer $($DevApiKey.Trim())";Accept="application/json";"Content-Type"="application/json"}
$decisions=Get-Content (Join-Path $PSScriptRoot "..\config\migration-decisions.json") -Raw|ConvertFrom-Json
$expectedWorkspaceId=[string]$decisions.dev_workspace_id
function Request{
  param([ValidateSet("Get","Post","Patch")][string]$Method,[string]$Path,[object]$Body)
  $p=@{Method=$Method;Uri="https://api.attio.com/v2$Path";Headers=$headers}
  if($null-ne$Body){$p.Body=[Text.Encoding]::UTF8.GetBytes(($Body|ConvertTo-Json -Depth 20))}
  Invoke-RestMethod @p
}
function Map($items){$m=@{};foreach($x in @($items)){$m[[string]$x.api_slug]=$x};return $m}
$deal=Request Get "/objects/deals" $null
if([string]$deal.data.api_slug-ne"deals"){throw "DEV standard Deals object was not found."}
$workspaceId=[string]$deal.data.id.workspace_id
if($workspaceId-ne$expectedWorkspaceId){throw "DEV workspace mismatch. Expected $expectedWorkspaceId but connected to $workspaceId."}
$attrs=Map @((Request Get "/objects/deals/attributes" $null).data)
$allAttrs=Map @((Request Get "/objects/deals/attributes?show_archived=true" $null).data)
function Clear-ArchivedSlug($slug,$title){
  if(-not $allAttrs.ContainsKey($slug)){return}
  $archived=$allAttrs[$slug]
  $archivedId=[string]$archived.id.attribute_id
  $legacySlug="$($slug)_legacy_$($archivedId.Substring(0,8))"
  $actions.Add("rename_archived_attribute:$($slug):$legacySlug")
  if($Apply){
    Request Patch "/objects/deals/attributes/$archivedId" @{data=@{title="$title (Legacy)";api_slug=$legacySlug;is_archived=$true}}|Out-Null
    Write-Host "RENAMED ARCHIVED: $slug -> $legacySlug"
  }else{Write-Host "DRY RUN: would rename archived $slug -> $legacySlug."}
  $allAttrs.Remove($slug)
}
$fields=@(
  [pscustomobject]@{Title="Buyer ID";Slug="buyer_id";Type="record-reference";Config=@{record_reference=@{allowed_objects=@("organizations","person")}};RenameFrom=$null},
  [pscustomobject]@{Title="Seller ID";Slug="seller_id";Type="record-reference";Config=@{record_reference=@{allowed_objects=@("organizations")}};RenameFrom=$null},
  [pscustomobject]@{Title="Stage Changed At";Slug="stage_changed_at";Type="timestamp";Config=@{};RenameFrom=$null},
  [pscustomobject]@{Title="Time In Stage (Days)";Slug="time_in_stage";Type="number";Config=@{};RenameFrom=$null},
  [pscustomobject]@{Title="NDA Count";Slug="nda_count";Type="number";Config=@{};RenameFrom=$null},
  [pscustomobject]@{Title="CIM Ready";Slug="cim_ready";Type="checkbox";Config=@{};RenameFrom=$null},
  [pscustomobject]@{Title="Deal Memo Ready";Slug="deal_memo_ready";Type="checkbox";Config=@{};RenameFrom=$null},
  [pscustomobject]@{Title="Contract Signed Date";Slug="contract_signed_date";Type="date";Config=@{};RenameFrom="exclusivity_start_date"},
  [pscustomobject]@{Title="Exclusivity Date";Slug="exclusivity_date";Type="date";Config=@{};RenameFrom="exclusivity_end_date"},
  [pscustomobject]@{Title="Data Room Substatus";Slug="data_room_substatus";Type="select";Config=@{};RenameFrom=$null},
  # Merged in from the retired Mandates list (2026-08-23 Mandate/Deal merge --
  # see migration-decisions.json). "phase" was deliberately left out: it's a
  # manually-typed label that only restates what universe_constructed/
  # universe_size/shortlist_approved/shortlist_size/tier1_contacted/responses
  # already show, and can silently drift out of sync with those numbers.
  [pscustomobject]@{Title="Deal Type";Slug="deal_type";Type="select";Config=@{};RenameFrom=$null;FixedOptions=@("Buy-side","Sell-side")},
  [pscustomobject]@{Title="Universe Constructed";Slug="universe_constructed";Type="checkbox";Config=@{};RenameFrom=$null},
  [pscustomobject]@{Title="Universe Size";Slug="universe_size";Type="number";Config=@{};RenameFrom=$null},
  [pscustomobject]@{Title="Shortlist Approved";Slug="shortlist_approved";Type="checkbox";Config=@{};RenameFrom=$null},
  [pscustomobject]@{Title="Shortlist Size";Slug="shortlist_size";Type="number";Config=@{};RenameFrom=$null},
  [pscustomobject]@{Title="Tier 1 Contacted";Slug="tier1_contacted";Type="number";Config=@{};RenameFrom=$null},
  [pscustomobject]@{Title="Responses";Slug="responses";Type="number";Config=@{};RenameFrom=$null},
  [pscustomobject]@{Title="Counterparty Interested";Slug="counterparty_interested";Type="number";Config=@{};RenameFrom=$null},
  [pscustomobject]@{Title="Mandate Start Date";Slug="start_date";Type="date";Config=@{};RenameFrom=$null},
  [pscustomobject]@{Title="Mandate Expiry Date";Slug="expiry_date";Type="date";Config=@{};RenameFrom=$null},
  [pscustomobject]@{Title="Retainer Amount";Slug="retainer_amount";Type="currency";Config=@{currency=@{default_currency_code="AED";display_type="symbol"}};RenameFrom=$null},
  [pscustomobject]@{Title="Source Mandate Entry ID";Slug="source_mandate_entry_id";Type="text";Config=@{};RenameFrom=$null},
  # Created directly via the API when first migrated (2026-07-19), never
  # tracked here until now -- added 2026-08-23 so drift/deletion gets caught
  # like every other field instead of silently trusted (same gap fixed for
  # Organization/Person/Buyer Role/Seller Role the same day).
  [pscustomobject]@{Title="Teaser Status";Slug="teaser_status";Type="select";Config=@{};RenameFrom=$null},
  [pscustomobject]@{Title="NDA Status";Slug="nda_status";Type="select";Config=@{};RenameFrom=$null},
  [pscustomobject]@{Title="Estimated Deal Value (AED)";Slug="estimated_deal_value_aed";Type="number";Config=@{};RenameFrom=$null},
  [pscustomobject]@{Title="Expected Close Date";Slug="expected_close_date";Type="date";Config=@{};RenameFrom=$null},
  [pscustomobject]@{Title="Fee %";Slug="fee";Type="number";Config=@{};RenameFrom=$null},
  # Only known multiselect among these custom Deal fields -- Multi=$true is
  # load-bearing, the drift check and create body below both key off it.
  [pscustomobject]@{Title="Assigned Advisor";Slug="assigned_advisor";Type="select";Multi=$true;Config=@{};RenameFrom=$null}
)
$actions=[Collections.Generic.List[string]]::new()
foreach($field in $fields){
  if($attrs.ContainsKey($field.Slug)){
    $current=$attrs[$field.Slug]
    if([string]$current.type-ne$field.Type-or[bool]$current.is_multiselect-ne[bool]$field.Multi){throw "DEV deals/$($field.Slug) has unexpected type or cardinality."}
    if([string]$current.title-ne$field.Title){
      $actions.Add("update_title:$($field.Slug):$($field.Title)")
      if($Apply){
        Request Patch "/objects/deals/attributes/$($current.id.attribute_id)" @{data=@{title=$field.Title}}|Out-Null
        Write-Host "RENAMED: $($field.Slug) -> $($field.Title)"
      }else{Write-Host "DRY RUN: would rename $($field.Slug) to '$($field.Title)'."}
    }else{Write-Host "EXISTS: $($field.Slug)"}
    continue
  }
  if($field.RenameFrom-and$attrs.ContainsKey($field.RenameFrom)){
    $current=$attrs[$field.RenameFrom]
    if([string]$current.type-ne$field.Type-or[bool]$current.is_multiselect-ne[bool]$field.Multi){throw "DEV deals/$($field.RenameFrom) has unexpected type or cardinality for rename to $($field.Slug)."}
    Clear-ArchivedSlug $field.Slug $field.Title
    $actions.Add("rename_attribute:$($field.RenameFrom):$($field.Slug)")
    if($Apply){
      Request Patch "/objects/deals/attributes/$($current.id.attribute_id)" @{data=@{title=$field.Title;api_slug=$field.Slug}}|Out-Null
      Write-Host "RENAMED: $($field.RenameFrom) -> $($field.Slug) ($($field.Title))"
    }else{Write-Host "DRY RUN: would rename $($field.RenameFrom) -> $($field.Slug) ($($field.Title))."}
    continue
  }
  Clear-ArchivedSlug $field.Slug $field.Title
  $actions.Add("create_attribute:$($field.Slug)")
  if($Apply){
    Request Post "/objects/deals/attributes" @{data=@{
      title=$field.Title;description="Wusool Deal target field.";api_slug=$field.Slug
      type=$field.Type;is_required=$false;is_unique=$false;is_multiselect=[bool]$field.Multi;config=$field.Config
    }}|Out-Null
    Write-Host "CREATED: $($field.Slug)"
  }else{Write-Host "DRY RUN: would create $($field.Slug) ($($field.Type))."}
}
if($Apply){$attrs=Map @((Request Get "/objects/deals/attributes" $null).data)}
foreach($field in @($fields|Where-Object{$_.Type-eq"select"-and$_.PSObject.Properties.Name-contains"FixedOptions"-and$_.FixedOptions})){
  if(-not$Apply-and-not$attrs.ContainsKey($field.Slug)){
    foreach($title in $field.FixedOptions){$actions.Add("create_option:$($field.Slug):$title");Write-Host "DRY RUN: would create $($field.Slug) option '$title'."}
    continue
  }
  $existingTitles=@{}
  foreach($o in @((Request Get "/objects/deals/attributes/$($field.Slug)/options" $null).data|Where-Object{-not$_.is_archived})){$existingTitles[[string]$o.title.Trim().ToLowerInvariant()]=$true}
  foreach($title in $field.FixedOptions){
    $key=$title.Trim().ToLowerInvariant()
    if($existingTitles.ContainsKey($key)){continue}
    $actions.Add("create_option:$($field.Slug):$title")
    if($Apply){
      Request Post "/objects/deals/attributes/$($field.Slug)/options" @{data=@{title=$title}}|Out-Null
      Write-Host "CREATED OPTION: $($field.Slug) -> $title"
    }else{Write-Host "DRY RUN: would create $($field.Slug) option '$title'."}
  }
}
# Idempotent: create the "Mandate Active" Deal stage whenever it's missing --
# the stage this merge uses for a signed mandate that's still sourcing, with
# no specific counterparty locked in yet (distinct from "Mandate Signed",
# which already implies a specific counterparty and signed terms).
$stageStatuses=@((Request Get "/objects/deals/attributes/stage/statuses" $null).data|Where-Object{-not$_.is_archived})
$hasMandateActive=@($stageStatuses|Where-Object{[string]$_.title.Trim().ToLowerInvariant()-eq"mandate active"}).Count-gt0
if(-not$hasMandateActive){
  $actions.Add("create_stage:Mandate Active")
  if($Apply){
    Request Post "/objects/deals/attributes/stage/statuses" @{data=@{title="Mandate Active"}}|Out-Null
    Write-Host "CREATED STAGE: Mandate Active"
  }else{Write-Host "DRY RUN: would create Deal stage 'Mandate Active'."}
}else{Write-Host "EXISTS: stage 'Mandate Active'"}
if($FailOnDrift-and$actions.Count){throw "Deal schema drift detected. Planned actions: $($actions.Count)."}
if($Apply){Write-Host "Deal schema apply complete."}else{Write-Host "Deal schema dry run complete. Planned actions: $($actions.Count)."}

}
function Invoke-BuyerRoleSchema {
param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [string]$DevApiKey = $env:DEV_ATTIO_API_KEY,
  [switch]$FailOnDrift,
  [switch]$Apply
)


$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($SourceApiKey)) {
  $SourceApiKey = [Environment]::GetEnvironmentVariable("SOURCE_ATTIO_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($DevApiKey)) {
  $DevApiKey = [Environment]::GetEnvironmentVariable("DEV_ATTIO_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($SourceApiKey)) { throw "Missing SOURCE_ATTIO_API_KEY." }
if ([string]::IsNullOrWhiteSpace($DevApiKey)) { throw "Missing DEV_ATTIO_API_KEY." }

$sourceHeaders = @{
  Authorization = "Bearer $($SourceApiKey.Trim())"
  Accept = "application/json"
  "Content-Type" = "application/json"
}
$devHeaders = @{
  Authorization = "Bearer $($DevApiKey.Trim())"
  Accept = "application/json"
  "Content-Type" = "application/json"
}

$decisions = Get-Content (Join-Path $PSScriptRoot "..\config\migration-decisions.json") -Raw |
  ConvertFrom-Json
$expectedWorkspaceId = [string]$decisions.dev_workspace_id

function Invoke-AttioRequest {
  param(
    [ValidateSet("Get", "Post", "Patch")][string]$Method,
    [hashtable]$Headers,
    [string]$Path,
    [object]$Body
  )
  $parameters = @{
    Method = $Method
    Uri = "https://api.attio.com/v2$Path"
    Headers = $Headers
  }
  if ($null -ne $Body) {
    $parameters.Body = [System.Text.Encoding]::UTF8.GetBytes(
      ($Body | ConvertTo-Json -Depth 30)
    )
  }
  Invoke-RestMethod @parameters
}

function Get-Map {
  param([object[]]$Items)
  $map = @{}
  foreach ($item in @($Items)) { $map[[string]$item.api_slug] = $item }
  return $map
}

function Get-OptionTitles {
  param([hashtable]$Headers, [string]$ListSlug, [string]$AttributeSlug)
  $response = Invoke-AttioRequest -Method Get -Headers $Headers `
    -Path "/lists/$ListSlug/attributes/$AttributeSlug/options"
  return @(
    $response.data |
      Where-Object { -not $_.is_archived -and $_.title } |
      ForEach-Object { [string]$_.title }
  )
}

$devOrganization = Invoke-AttioRequest -Method Get -Headers $devHeaders `
  -Path "/objects/organizations"

$connectedWorkspaceId = [string]$devOrganization.data.id.workspace_id
if ($connectedWorkspaceId -ne $expectedWorkspaceId) {
  throw "DEV workspace mismatch. Expected $expectedWorkspaceId but connected to $connectedWorkspaceId."
}
$devPerson = Invoke-AttioRequest -Method Get -Headers $devHeaders -Path "/objects/person"
if ([string]$devPerson.data.api_slug -ne "person") {
  throw "The DEV custom Person object slug is not person."
}

$sourceList = Invoke-AttioRequest -Method Get -Headers $sourceHeaders -Path "/lists/buyer_brain"
if ([string]$sourceList.data.api_slug -ne "buyer_brain") {
  throw "SOURCE buyer_brain list was not found."
}

$devLists = Invoke-AttioRequest -Method Get -Headers $devHeaders -Path "/lists"
$devListMap = Get-Map -Items @($devLists.data)
$actions = [System.Collections.Generic.List[string]]::new()

if (-not $devListMap.ContainsKey("buyer_role")) {
  $actions.Add("create_list:buyer_role")
  if (-not $Apply) {
    Write-Host "DRY RUN: would create DEV buyer_role parented to organizations."
  } else {
    Invoke-AttioRequest -Method Post -Headers $devHeaders -Path "/lists" -Body @{
      data = @{
        name = "Buyer Role"
        api_slug = "buyer_role"
        parent_object = "organizations"
        workspace_access = "full-access"
        workspace_member_access = @()
      }
    } | Out-Null
    Write-Host "CREATED: buyer_role list"
  }
} else {
  $parentObjects = @($devListMap["buyer_role"].parent_object)
  if ($parentObjects -notcontains "organizations") {
    throw "DEV buyer_role has the wrong parent object: $($parentObjects -join ', ')."
  }
  Write-Host "EXISTS: buyer_role list parented to organizations"
}

$fields = @(
  [pscustomobject]@{ Title="Buyer Model"; Slug="model"; Type="select"; Multi=$false; SourceOption="buyer_model"; Config=@{} },
  [pscustomobject]@{ Title="Mandate Status"; Slug="mandate_status"; Type="select"; Multi=$false; SourceOption="mandate_status"; Config=@{} },
  [pscustomobject]@{ Title="EBITDA Floor"; Slug="ebitda_floor"; Type="currency"; Multi=$false; SourceOption=$null; Config=@{ currency=@{ default_currency_code="AED"; display_type="symbol" } } },
  [pscustomobject]@{ Title="Check Size Min"; Slug="check_size_min"; Type="currency"; Multi=$false; SourceOption=$null; Config=@{ currency=@{ default_currency_code="AED"; display_type="symbol" } } },
  [pscustomobject]@{ Title="Check Size Max"; Slug="check_size_max"; Type="currency"; Multi=$false; SourceOption=$null; Config=@{ currency=@{ default_currency_code="AED"; display_type="symbol" } } },
  [pscustomobject]@{ Title="EV Ceiling"; Slug="ev_ceiling"; Type="currency"; Multi=$false; SourceOption=$null; Config=@{ currency=@{ default_currency_code="AED"; display_type="symbol" } } },
  [pscustomobject]@{ Title="Deal Structure Tolerance"; Slug="deal_structure_tolerance"; Type="select"; Multi=$false; SourceOption=$null; FixedOptions=@("Majority","Minority","Flexible","Acquisition Financing"); Config=@{} },
  [pscustomobject]@{ Title="Earnout Tolerance"; Slug="earnout_tolerance"; Type="checkbox"; Multi=$false; SourceOption=$null; Config=@{} },
  [pscustomobject]@{ Title="Profitable Only"; Slug="profitable_only"; Type="checkbox"; Multi=$false; SourceOption=$null; Config=@{} },
  [pscustomobject]@{ Title="Investment Strategy"; Slug="investment_strategy"; Type="text"; Multi=$false; SourceOption=$null; Config=@{} },
  [pscustomobject]@{ Title="Notes"; Slug="notes"; Type="text"; Multi=$false; SourceOption=$null; Config=@{} },
  [pscustomobject]@{ Title="Key Contact"; Slug="key_contact"; Type="record-reference"; Multi=$false; SourceOption=$null; Config=@{ record_reference=@{ allowed_objects=@("person") } } },
  [pscustomobject]@{ Title="Acquisition Enrichment"; Slug="acquisition_enrichment"; Type="text"; Multi=$false; SourceOption=$null; Config=@{} },
  [pscustomobject]@{ Title="Deals Introduced"; Slug="deals_introduced"; Type="number"; Multi=$false; SourceOption=$null; Config=@{} },
  [pscustomobject]@{ Title="Deals Converted"; Slug="deals_converted"; Type="number"; Multi=$false; SourceOption=$null; Config=@{} },
  # Created directly via the API when first migrated (2026-08-19), never
  # tracked here until now -- added 2026-08-23 so drift/deletion gets caught
  # like every other field instead of silently trusted (same gap fixed for
  # Organization/Person the same day).
  [pscustomobject]@{ Title="EBITDA Ceiling"; Slug="ebitda_ceiling"; Type="currency"; Multi=$false; SourceOption=$null; Config=@{ currency=@{ default_currency_code="AED"; display_type="symbol" } } },
  [pscustomobject]@{ Title="Estimated AUM"; Slug="estimated_aum"; Type="currency"; Multi=$false; SourceOption=$null; Config=@{ currency=@{ default_currency_code="USD"; display_type="symbol" } } },
  [pscustomobject]@{ Title="Notable Investments"; Slug="notable_investments"; Type="text"; Multi=$false; SourceOption=$null; Config=@{} },
  [pscustomobject]@{ Title="Key Personnel"; Slug="key_personnel"; Type="text"; Multi=$false; SourceOption=$null; Config=@{} },
  [pscustomobject]@{ Title="Relationship Warmth"; Slug="relationship_warmth"; Type="select"; Multi=$false; SourceOption="relationship_warmth"; Config=@{} },
  [pscustomobject]@{ Title="Target Geography"; Slug="target_geography"; Type="select"; Multi=$true; SourceOption="target_geography"; Config=@{} },
  [pscustomobject]@{ Title="Last Mandate Briefing Date"; Slug="last_mandate_briefing_date"; Type="date"; Multi=$false; SourceOption=$null; Config=@{} },
  [pscustomobject]@{ Title="Prior GCC Acquisition"; Slug="prior_gcc_acquisition"; Type="text"; Multi=$false; SourceOption=$null; Config=@{} },
  [pscustomobject]@{ Title="Is Active"; Slug="is_active"; Type="checkbox"; Multi=$false; SourceOption=$null; Config=@{} },
  [pscustomobject]@{ Title="Legacy Entry ID"; Slug="legacy_entry_id"; Type="text"; Multi=$false; SourceOption=$null; Config=@{} }
)

if ($Apply -and -not $devListMap.ContainsKey("buyer_role")) {
  $devLists = Invoke-AttioRequest -Method Get -Headers $devHeaders -Path "/lists"
  $devListMap = Get-Map -Items @($devLists.data)
}

$attributes = @{}
if ($devListMap.ContainsKey("buyer_role")) {
  $attributeResponse = Invoke-AttioRequest -Method Get -Headers $devHeaders `
    -Path "/lists/buyer_role/attributes"
  $attributes = Get-Map -Items @($attributeResponse.data)
}

foreach ($field in $fields) {
  if ($attributes.ContainsKey($field.Slug)) {
    $current = $attributes[$field.Slug]
    if ([string]$current.type -ne $field.Type -or
        [bool]$current.is_multiselect -ne [bool]$field.Multi) {
      if ($field.Slug -ne "deal_structure_tolerance" -or [string]$current.type -ne "text") {
        throw "DEV buyer_role/$($field.Slug) has type=$($current.type), multiselect=$($current.is_multiselect); expected $($field.Type), multiselect=$($field.Multi)."
      }
      $currentId = [string]$current.id.attribute_id
      $legacySlug = "deal_structure_tolerance_legacy_$($currentId.Substring(0, 8))"
      $actions.Add("archive_text_attribute:deal_structure_tolerance:$legacySlug")
      if ($Apply) {
        Invoke-AttioRequest -Method Patch -Headers $devHeaders `
          -Path "/lists/buyer_role/attributes/$currentId" `
          -Body @{ data = @{
            title = "Deal Structure Tolerance (Legacy Text)"
            api_slug = $legacySlug
            is_archived = $true
          } } | Out-Null
        Write-Host "ARCHIVED: deal_structure_tolerance -> $legacySlug"
      } else {
        Write-Host "DRY RUN: would archive legacy text deal_structure_tolerance -> $legacySlug, then create a select attribute at the original slug."
      }
      $attributes.Remove($field.Slug)
    } else {
      Write-Host "EXISTS: $($field.Slug)"
      continue
    }
  }

  $actions.Add("create_attribute:$($field.Slug)")
  if (-not $Apply) {
    Write-Host "DRY RUN: would create $($field.Slug) ($($field.Type))."
    continue
  }

  Invoke-AttioRequest -Method Post -Headers $devHeaders `
    -Path "/lists/buyer_role/attributes" -Body @{
      data = @{
        title = $field.Title
        description = "Wusool Buyer Role target field."
        api_slug = $field.Slug
        type = $field.Type
        is_required = $false
        is_unique = $false
        is_multiselect = [bool]$field.Multi
        config = $field.Config
      }
    } | Out-Null
  Write-Host "CREATED: $($field.Slug)"
}

if ($Apply) {
  $attributeResponse = Invoke-AttioRequest -Method Get -Headers $devHeaders `
    -Path "/lists/buyer_role/attributes"
  $attributes = Get-Map -Items @($attributeResponse.data)
}

foreach ($field in @($fields | Where-Object SourceOption)) {
  if (-not $Apply -and -not $attributes.ContainsKey($field.Slug)) {
    $sourceTitles = Get-OptionTitles -Headers $sourceHeaders `
      -ListSlug "buyer_brain" -AttributeSlug $field.SourceOption
    foreach ($title in $sourceTitles) {
      $actions.Add("create_option:$($field.Slug):$title")
      Write-Host "DRY RUN: would create $($field.Slug) option '$title'."
    }
    continue
  }

  $sourceTitles = Get-OptionTitles -Headers $sourceHeaders `
    -ListSlug "buyer_brain" -AttributeSlug $field.SourceOption
  $targetTitles = Get-OptionTitles -Headers $devHeaders `
    -ListSlug "buyer_role" -AttributeSlug $field.Slug
  $existing = @{}
  foreach ($title in $targetTitles) { $existing[$title.Trim().ToLowerInvariant()] = $true }
  foreach ($title in $sourceTitles) {
    $key = $title.Trim().ToLowerInvariant()
    if ($existing.ContainsKey($key)) { continue }
    $actions.Add("create_option:$($field.Slug):$title")
    if (-not $Apply) {
      Write-Host "DRY RUN: would create $($field.Slug) option '$title'."
    } else {
      Invoke-AttioRequest -Method Post -Headers $devHeaders `
        -Path "/lists/buyer_role/attributes/$($field.Slug)/options" `
        -Body @{ data = @{ title = $title } } | Out-Null
      Write-Host "CREATED OPTION: $($field.Slug) -> $title"
    }
  }
}

foreach ($field in @($fields | Where-Object FixedOptions)) {
  if (-not $Apply -and -not $attributes.ContainsKey($field.Slug)) {
    foreach ($title in $field.FixedOptions) {
      $actions.Add("create_option:$($field.Slug):$title")
      Write-Host "DRY RUN: would create $($field.Slug) option '$title'."
    }
    continue
  }

  $targetTitles = Get-OptionTitles -Headers $devHeaders `
    -ListSlug "buyer_role" -AttributeSlug $field.Slug
  $existing = @{}
  foreach ($title in $targetTitles) { $existing[$title.Trim().ToLowerInvariant()] = $true }
  foreach ($title in $field.FixedOptions) {
    $key = $title.Trim().ToLowerInvariant()
    if ($existing.ContainsKey($key)) { continue }
    $actions.Add("create_option:$($field.Slug):$title")
    if (-not $Apply) {
      Write-Host "DRY RUN: would create $($field.Slug) option '$title'."
    } else {
      Invoke-AttioRequest -Method Post -Headers $devHeaders `
        -Path "/lists/buyer_role/attributes/$($field.Slug)/options" `
        -Body @{ data = @{ title = $title } } | Out-Null
      Write-Host "CREATED OPTION: $($field.Slug) -> $title"
    }
  }
}

Write-Host ""
if ($FailOnDrift -and $actions.Count -gt 0) {
  throw "Buyer Role schema drift detected. Planned actions: $($actions.Count)."
}
if ($Apply) {
  Write-Host "Buyer Role schema apply complete."
} else {
  Write-Host "Buyer Role schema dry run complete. Planned actions: $($actions.Count)."
}

}
function Invoke-SellerRoleSchema {
param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [string]$DevApiKey = $env:DEV_ATTIO_API_KEY,
  [switch]$FailOnDrift,
  [switch]$Apply
)


$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($SourceApiKey)) {
  $SourceApiKey = [Environment]::GetEnvironmentVariable("SOURCE_ATTIO_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($DevApiKey)) {
  $DevApiKey = [Environment]::GetEnvironmentVariable("DEV_ATTIO_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($SourceApiKey)) { throw "Missing SOURCE_ATTIO_API_KEY." }
if ([string]::IsNullOrWhiteSpace($DevApiKey)) { throw "Missing DEV_ATTIO_API_KEY." }

$sourceHeaders = @{
  Authorization = "Bearer $($SourceApiKey.Trim())"
  Accept = "application/json"
  "Content-Type" = "application/json"
}
$devHeaders = @{
  Authorization = "Bearer $($DevApiKey.Trim())"
  Accept = "application/json"
  "Content-Type" = "application/json"
}

$decisions = Get-Content (Join-Path $PSScriptRoot "..\config\migration-decisions.json") -Raw |
  ConvertFrom-Json
$expectedWorkspaceId = [string]$decisions.dev_workspace_id

function Invoke-AttioRequest {
  param(
    [ValidateSet("Get", "Post", "Patch")][string]$Method,
    [hashtable]$Headers,
    [string]$Path,
    [object]$Body
  )
  $parameters = @{
    Method = $Method
    Uri = "https://api.attio.com/v2$Path"
    Headers = $Headers
  }
  if ($null -ne $Body) {
    $parameters.Body = [Text.Encoding]::UTF8.GetBytes(
      ($Body | ConvertTo-Json -Depth 30)
    )
  }
  Invoke-RestMethod @parameters
}

function Get-Map {
  param([object[]]$Items)
  $map = @{}
  foreach ($item in @($Items)) { $map[[string]$item.api_slug] = $item }
  return $map
}

function Get-OptionTitles {
  param([hashtable]$Headers, [string]$ListSlug, [string]$AttributeSlug)
  $response = Invoke-AttioRequest -Method Get -Headers $Headers `
    -Path "/lists/$ListSlug/attributes/$AttributeSlug/options"
  return @(
    $response.data |
      Where-Object { -not $_.is_archived -and $_.title } |
      ForEach-Object { [string]$_.title }
  )
}

$devOrganization = Invoke-AttioRequest -Method Get -Headers $devHeaders `
  -Path "/objects/organizations"
$connectedWorkspaceId = [string]$devOrganization.data.id.workspace_id
if ($connectedWorkspaceId -ne $expectedWorkspaceId) {
  throw "DEV workspace mismatch. Expected $expectedWorkspaceId but connected to $connectedWorkspaceId."
}

$sourceList = Invoke-AttioRequest -Method Get -Headers $sourceHeaders `
  -Path "/lists/valuation_tool_leads"
if ([string]$sourceList.data.api_slug -ne "valuation_tool_leads" -or
    @($sourceList.data.parent_object) -notcontains "companies") {
  throw "SOURCE valuation_tool_leads is missing or is not parented to companies."
}

$devLists = Invoke-AttioRequest -Method Get -Headers $devHeaders -Path "/lists"
$devListMap = Get-Map -Items @($devLists.data)
$actions = [System.Collections.Generic.List[string]]::new()

if (-not $devListMap.ContainsKey("seller_role")) {
  $actions.Add("create_list:seller_role")
  if (-not $Apply) {
    Write-Host "DRY RUN: would create DEV seller_role parented to organizations."
  } else {
    Invoke-AttioRequest -Method Post -Headers $devHeaders -Path "/lists" -Body @{
      data = @{
        name = "Seller Role"
        api_slug = "seller_role"
        parent_object = "organizations"
        workspace_access = "full-access"
        workspace_member_access = @()
      }
    } | Out-Null
    Write-Host "CREATED: seller_role list"
  }
} else {
  $parentObjects = @($devListMap["seller_role"].parent_object)
  if ($parentObjects -notcontains "organizations") {
    throw "DEV seller_role has the wrong parent object: $($parentObjects -join ', ')."
  }
  Write-Host "EXISTS: seller_role list parented to organizations"
}

$fields = @(
  [pscustomobject]@{ Title="Outreach Tier"; Slug="outreach_tier"; Type="select"; SourceOptions=@("outreach_tier"); Config=@{} },
  [pscustomobject]@{ Title="Appetite Signal"; Slug="appetite_signal"; Type="select"; SourceOptions=@("seller_appetite_signal"); Config=@{} },
  [pscustomobject]@{ Title="Relationship Status"; Slug="relationship_status"; Type="select"; SourceOptions=@("relationship_status"); Config=@{} },
  [pscustomobject]@{ Title="Estimated Revenue"; Slug="est_revenue"; Type="currency"; SourceOptions=@(); Config=@{ currency=@{ default_currency_code="AED"; display_type="symbol" } } },
  [pscustomobject]@{ Title="Estimated EBITDA"; Slug="est_ebitda"; Type="currency"; SourceOptions=@(); Config=@{ currency=@{ default_currency_code="AED"; display_type="symbol" } } },
  [pscustomobject]@{ Title="Owner Salary"; Slug="owner_salary"; Type="currency"; SourceOptions=@(); Config=@{ currency=@{ default_currency_code="AED"; display_type="symbol" } } },
  [pscustomobject]@{ Title="Valuation Low"; Slug="valuation_low"; Type="currency"; SourceOptions=@(); Config=@{ currency=@{ default_currency_code="AED"; display_type="symbol" } } },
  [pscustomobject]@{ Title="Valuation Mid"; Slug="valuation_mid"; Type="currency"; SourceOptions=@(); Config=@{ currency=@{ default_currency_code="AED"; display_type="symbol" } } },
  [pscustomobject]@{ Title="Valuation High"; Slug="valuation_high"; Type="currency"; SourceOptions=@(); Config=@{ currency=@{ default_currency_code="AED"; display_type="symbol" } } },
  [pscustomobject]@{ Title="Sell Timeline"; Slug="sell_timeline"; Type="select"; SourceOptions=@(); TargetOptions=@("Immediate","Within 6 Months","6-12 Months","12-24 Months","Not Selling"); Config=@{} },
  [pscustomobject]@{ Title="Readiness Score"; Slug="readiness_score"; Type="number"; SourceOptions=@(); Config=@{} },
  [pscustomobject]@{ Title="Readiness Band"; Slug="readiness_band"; Type="select"; SourceOptions=@(); Config=@{} },
  [pscustomobject]@{ Title="Last Attempt Date"; Slug="last_attempt_date"; Type="date"; SourceOptions=@(); Config=@{} },
  [pscustomobject]@{ Title="Last Attempt Channel"; Slug="last_attempt_channel"; Type="select"; SourceOptions=@("attempt_1_channel","attempt_2_channel","attempt_2_channel_6"); Config=@{} },
  [pscustomobject]@{ Title="Last Attempt Outcome"; Slug="last_attempt_outcome"; Type="select"; SourceOptions=@("attempt_1_outcome","attempt_2_outcome","attempt_2_outcome_6"); Config=@{} },
  [pscustomobject]@{ Title="Lead Quality Score"; Slug="lead_quality_score"; Type="number"; SourceOptions=@(); Config=@{} },
  [pscustomobject]@{ Title="Re-Engage Date"; Slug="re_engage_date"; Type="date"; SourceOptions=@(); Config=@{} },
  # Created directly via the API when first migrated (2026-08-17), never
  # tracked here until now -- added 2026-08-23 so drift/deletion gets caught
  # like every other field instead of silently trusted (same gap fixed for
  # Organization/Person/Buyer Role the same day).
  [pscustomobject]@{ Title="Is Active"; Slug="is_active"; Type="checkbox"; SourceOptions=@(); Config=@{} },
  [pscustomobject]@{ Title="Legacy Entry ID"; Slug="legacy_entry_id"; Type="text"; SourceOptions=@(); Config=@{} }
)

if ($Apply -and -not $devListMap.ContainsKey("seller_role")) {
  $devLists = Invoke-AttioRequest -Method Get -Headers $devHeaders -Path "/lists"
  $devListMap = Get-Map -Items @($devLists.data)
}

$attributes = @{}
if ($devListMap.ContainsKey("seller_role")) {
  $attributeResponse = Invoke-AttioRequest -Method Get -Headers $devHeaders `
    -Path "/lists/seller_role/attributes"
  $attributes = Get-Map -Items @($attributeResponse.data)
}

foreach ($field in $fields) {
  if ($attributes.ContainsKey($field.Slug)) {
    $current = $attributes[$field.Slug]
    if ([string]$current.type -ne $field.Type -or [bool]$current.is_multiselect) {
      throw "DEV seller_role/$($field.Slug) has unexpected type or cardinality."
    }
    Write-Host "EXISTS: $($field.Slug)"
    continue
  }

  $actions.Add("create_attribute:$($field.Slug)")
  if (-not $Apply) {
    Write-Host "DRY RUN: would create $($field.Slug) ($($field.Type))."
    continue
  }
  Invoke-AttioRequest -Method Post -Headers $devHeaders `
    -Path "/lists/seller_role/attributes" -Body @{
      data = @{
        title = $field.Title
        description = "Wusool Seller Role target field."
        api_slug = $field.Slug
        type = $field.Type
        is_required = $false
        is_unique = $false
        is_multiselect = $false
        config = $field.Config
      }
    } | Out-Null
  Write-Host "CREATED: $($field.Slug)"
}

if ($Apply) {
  $attributeResponse = Invoke-AttioRequest -Method Get -Headers $devHeaders `
    -Path "/lists/seller_role/attributes"
  $attributes = Get-Map -Items @($attributeResponse.data)
}

foreach ($field in @($fields | Where-Object { @($_.SourceOptions).Count -gt 0 -or @($_.TargetOptions).Count -gt 0 })) {
  $sourceTitles = @(
    @($field.TargetOptions)
    foreach ($sourceSlug in @($field.SourceOptions)) {
      Get-OptionTitles -Headers $sourceHeaders `
        -ListSlug "valuation_tool_leads" -AttributeSlug $sourceSlug
    }
  ) | Sort-Object -Unique

  if (-not $Apply -and -not $attributes.ContainsKey($field.Slug)) {
    foreach ($title in $sourceTitles) {
      $actions.Add("create_option:$($field.Slug):$title")
      Write-Host "DRY RUN: would create $($field.Slug) option '$title'."
    }
    continue
  }

  $targetOptions = @((Invoke-AttioRequest -Method Get -Headers $devHeaders `
        -Path "/lists/seller_role/attributes/$($field.Slug)/options").data |
      Where-Object { -not $_.is_archived -and $_.title })
  $existing = @{}
  foreach ($option in $targetOptions) { $existing[$option.title.Trim().ToLowerInvariant()] = $option }
  foreach ($title in $sourceTitles) {
    $key = $title.Trim().ToLowerInvariant()
    if ($existing.ContainsKey($key)) {
      $current = $existing[$key]
      if ([string]$current.title -cne $title) {
        # Same option case-insensitively, but the exact casing drifted from
        # the approved title (e.g. a legacy "direct" vs approved "Direct").
        # Rename in place rather than archive+create, so existing entry
        # associations to this option are preserved.
        $actions.Add("rename_option:$($field.Slug):$($current.title)->$title")
        if ($Apply) {
          Invoke-AttioRequest -Method Patch -Headers $devHeaders `
            -Path "/lists/seller_role/attributes/$($field.Slug)/options/$([string]$current.id.option_id)" `
            -Body @{ data = @{ title = $title } } | Out-Null
          Write-Host "RENAMED OPTION: $($field.Slug) -> '$($current.title)' to '$title'"
        } else {
          Write-Host "DRY RUN: would rename $($field.Slug) option '$($current.title)' to '$title'."
        }
      }
      continue
    }
    $actions.Add("create_option:$($field.Slug):$title")
    if (-not $Apply) {
      Write-Host "DRY RUN: would create $($field.Slug) option '$title'."
    } else {
      Invoke-AttioRequest -Method Post -Headers $devHeaders `
        -Path "/lists/seller_role/attributes/$($field.Slug)/options" `
        -Body @{ data = @{ title = $title } } | Out-Null
      Write-Host "CREATED OPTION: $($field.Slug) -> $title"
    }
  }
}

# TargetOptions fields declare a closed, approved option set (unlike
# SourceOptions fields, which intentionally grow from SOURCE data over
# time). Archive any active option that is no longer in that approved set,
# so stale/unapproved options (e.g. a superseded value) don't linger in the
# dropdown after a decision changes the approved list.
foreach ($field in @($fields | Where-Object { $_.TargetOptions -and @($_.TargetOptions).Count -gt 0 })) {
  if (-not $Apply -and -not $attributes.ContainsKey($field.Slug)) { continue }
  $approved = @{}
  foreach ($title in @($field.TargetOptions)) { $approved[$title.Trim().ToLowerInvariant()] = $true }
  $existingOptions = @((Invoke-AttioRequest -Method Get -Headers $devHeaders `
        -Path "/lists/seller_role/attributes/$($field.Slug)/options").data |
      Where-Object { -not $_.is_archived -and $_.title })
  foreach ($option in $existingOptions) {
    $key = $option.title.Trim().ToLowerInvariant()
    if ($approved.ContainsKey($key)) { continue }
    $optionId = [string]$option.id.option_id
    $actions.Add("archive_option:$($field.Slug):$($option.title)")
    if (-not $Apply) {
      Write-Host "DRY RUN: would archive stale $($field.Slug) option '$($option.title)'."
    } else {
      Invoke-AttioRequest -Method Patch -Headers $devHeaders `
        -Path "/lists/seller_role/attributes/$($field.Slug)/options/$optionId" `
        -Body @{ data = @{ is_archived = $true } } | Out-Null
      Write-Host "ARCHIVED OPTION: $($field.Slug) -> $($option.title)"
    }
  }
}

Write-Host ""
if ($FailOnDrift -and $actions.Count -gt 0) {
  throw "Seller Role schema drift detected. Planned actions: $($actions.Count)."
}
if ($Apply) {
  Write-Host "Seller Role schema apply complete."
} else {
  Write-Host "Seller Role schema dry run complete. Planned actions: $($actions.Count)."
}

}
$args=@{DevApiKey=$DevApiKey};if($Entity-ne"deals"){$args.SourceApiKey=$SourceApiKey};if($FailOnDrift-and$Entity-in@("deals","buyer_role","seller_role")){$args.FailOnDrift=$true};if($Apply){$args.Apply=$true}
switch($Entity){"organizations"{Invoke-OrganizationSchema @args};"person"{Invoke-PersonSchema @args};"deals"{Invoke-DealSchema @args};"buyer_role"{Invoke-BuyerRoleSchema @args};"seller_role"{Invoke-SellerRoleSchema @args}}
