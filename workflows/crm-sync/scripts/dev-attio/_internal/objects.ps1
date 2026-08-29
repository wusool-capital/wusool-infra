param(
 [ValidateSet("record","parallel","deals")][string]$Task,
 [ValidateSet("organizations","person")][string]$Object="organizations",
 [string]$SourceApiKey=$env:SOURCE_ATTIO_API_KEY,[string]$DevApiKey=$env:DEV_ATTIO_API_KEY,
 [int]$Limit=10,[int]$StartOffset=0,[int]$PageSize=100,[int]$Workers=4,
 [string]$DevOwnerWorkspaceMemberId,[string]$Confirmation,[switch]$ExistingOnly,[switch]$DeleteOrphaned,[switch]$MigrateMandates,[switch]$Apply
)
$ErrorActionPreference="Stop"
function Invoke-ObjectRecord {
param(
  [ValidateSet("organizations", "person")]
  [string]$Object = "organizations",
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [string]$DevApiKey = $env:DEV_ATTIO_API_KEY,
  [int]$Limit = 10,
  [int]$StartOffset = 0,
  [int]$PageSize = 100,
  [switch]$Apply
)


$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($SourceApiKey)) {
  throw "Missing SOURCE_ATTIO_API_KEY."
}
if ([string]::IsNullOrWhiteSpace($DevApiKey)) {
  throw "Missing DEV_ATTIO_API_KEY."
}
if ($Limit -lt 0) {
  throw "Limit cannot be negative. Use 0 to process all records."
}
if ($StartOffset -lt 0) {
  throw "StartOffset cannot be negative."
}

$isPerson = $Object -eq "person"
$sourceObjectSlug = if ($isPerson) { "people" } else { "companies" }
$targetObjectSlug = if ($isPerson) { "person" } else { "organizations" }
$entityName = if ($isPerson) { "Person" } else { "Organization" }

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

$decisions = Get-Content (Join-Path $PSScriptRoot "..\config\migration-decisions.json") -Raw | ConvertFrom-Json
$ownerCrosswalkByName = @{}
foreach ($entry in @($decisions.workspace_member_crosswalk.mapping)) {
  $firstName = ([string]$entry.source_name).Split(" ")[0].Trim().ToLowerInvariant()
  if (-not [string]::IsNullOrWhiteSpace($firstName)) {
    $ownerCrosswalkByName[$firstName] = [string]$entry.dev_workspace_member_id
  }
}

function Invoke-AttioRequest {
  param(
    [ValidateSet("Get", "Post", "Patch", "Put")]
    [string]$Method,
    [hashtable]$Headers,
    [string]$Path,
    [object]$Body
  )

  for ($attempt = 1; $attempt -le 8; $attempt++) {
    try {
      $parameters = @{
        Method = $Method
        Uri = "https://api.attio.com/v2$Path"
        Headers = $Headers
      }
      if ($null -ne $Body) {
        $parameters.Body = [System.Text.Encoding]::UTF8.GetBytes(
          ($Body | ConvertTo-Json -Depth 80)
        )
      }
      return Invoke-RestMethod @parameters
    } catch {
      $statusCode = 0
      if ($_.Exception.Response) {
        $statusCode = [int]$_.Exception.Response.StatusCode
      }
      if ($attempt -eq 8 -or ($statusCode -ne 429 -and $statusCode -lt 500)) {
        throw
      }
      $delay = [Math]::Min(60, 5 * $attempt)
      Write-Warning "Attio $Method $Path returned HTTP $statusCode. Retrying in $delay seconds."
      Start-Sleep -Seconds $delay
    }
  }
}

function Get-AttributeMap {
  param([hashtable]$Headers, [string]$ObjectSlug)

  $response = Invoke-AttioRequest -Method Get -Headers $Headers `
    -Path "/objects/$ObjectSlug/attributes"
  $map = @{}
  foreach ($attribute in @($response.data)) {
    if (-not [string]::IsNullOrWhiteSpace($attribute.api_slug)) {
      $map[[string]$attribute.api_slug] = $attribute
    }
  }
  return $map
}

function Get-RecordId {
  param([object]$Record)

  if ($Record.id.record_id) {
    return [string]$Record.id.record_id
  }
  return [string]$Record.record_id
}

function Get-ScalarValue {
  param([object]$Item)

  if ($null -eq $Item) { return $null }
  if ($Item.attribute_type -eq "interaction" -and $Item.active_from) {
    return [string]$Item.active_from
  }
  # Checked before the location heuristic below: an Attio phone-number item
  # also carries its own `country_code` (e.g. "AE") alongside `phone_number`
  # -- the location branch's `-or $Item.country_code` fallback used to match
  # phone items too and return a raw ordered-dictionary location object
  # instead of the phone string, which then serialized as the literal text
  # "System.Collections.Specialized.OrderedDictionary" once written to DEV.
  # A genuine location item never has these three fields set, so checking
  # them first is always safe.
  if ($Item.full_name) { return [string]$Item.full_name }
  if ($Item.email_address) { return [string]$Item.email_address }
  if ($Item.phone_number) { return [string]$Item.phone_number }
  if ($Item.attribute_type -eq "location" -or $Item.country_code) {
    $location = [ordered]@{}
    foreach ($property in @(
      "line_1",
      "line_2",
      "line_3",
      "line_4",
      "locality",
      "region",
      "postcode",
      "country_code",
      "latitude",
      "longitude"
    )) {
      if ($null -ne $Item.$property -and
          -not [string]::IsNullOrWhiteSpace([string]$Item.$property)) {
        $location[$property] = $Item.$property
      }
    }
    if ($location.Count -gt 0) {
      return $location
    }
  }
  if ($null -ne $Item.value) { return $Item.value }
  if ($Item.option.title) { return [string]$Item.option.title }
  if ($Item.status.title) { return [string]$Item.status.title }
  if ($Item.domain) { return [string]$Item.domain }
  if ($Item.title) { return [string]$Item.title }
  if ($Item.country) { return [string]$Item.country }
  if ($null -ne $Item.currency_value) { return [decimal]$Item.currency_value }
  return $null
}

function Get-SourceValues {
  param([object]$Values, [string]$Slug)

  $result = @()
  foreach ($item in @($Values.$Slug)) {
    $value = Get-ScalarValue -Item $item
    if ($null -ne $value -and -not [string]::IsNullOrWhiteSpace([string]$value)) {
      $result += $value
    }
  }
  return @($result)
}

function Get-NormalizedRelationshipStatus {
  param([object]$Values)

  $mapped = @()
  foreach ($item in @($Values.relationship_status)) {
    $sourceTitle = [string](Get-ScalarValue -Item $item)
    if ([string]::IsNullOrWhiteSpace($sourceTitle)) { continue }

    $targetTitle = switch ($sourceTitle.Trim().ToLowerInvariant()) {
      "reached out" { "Warm" }
      "warm" { "Warm" }
      "active" { "Warm" }
      "cold" { "Cold" }
      "inactive" { "Cold" }
      "not contacted" { "Cold" }
      "hold" { "Cold" }
      "closed" { "Closed" }
      default { throw "Unapproved Relationship Status value '$sourceTitle'." }
    }

    $activeFrom = $null
    if ($item.active_from) {
      $parsed = [datetimeoffset]::MinValue
      if ([datetimeoffset]::TryParse([string]$item.active_from, [ref]$parsed)) {
        $activeFrom = $parsed
      }
    }
    $mapped += [pscustomobject]@{
      Source = $sourceTitle
      Target = $targetTitle
      ActiveFrom = $activeFrom
    }
  }

  if ($mapped.Count -eq 0) { return $null }
  $distinctTargets = @($mapped.Target | Sort-Object -Unique)
  if ($distinctTargets.Count -eq 1) { return [string]$distinctTargets[0] }

  if (@($mapped | Where-Object { $null -eq $_.ActiveFrom }).Count -gt 0) {
    throw "Conflicting Relationship Status values have a missing active_from timestamp: $($mapped.Source -join ', ')."
  }

  $ordered = @($mapped | Sort-Object ActiveFrom -Descending)
  if ($ordered.Count -gt 1 -and $ordered[0].ActiveFrom -eq $ordered[1].ActiveFrom -and
      $ordered[0].Target -ne $ordered[1].Target) {
    throw "Conflicting Relationship Status values have tied active_from timestamps: $($mapped.Source -join ', ')."
  }
  return [string]$ordered[0].Target
}

function Get-SourceReferenceIds {
  param([object]$Values, [string[]]$Slugs)

  $ids = @()
  foreach ($slug in $Slugs) {
    foreach ($item in @($Values.$slug)) {
      if ($item.target_record_id) {
        $ids += [string]$item.target_record_id
      }
    }
    if ($ids.Count -gt 0) { break }
  }
  return @($ids | Select-Object -Unique)
}

function Get-HqCountry {
  param([object]$Values)

  $location = @($Values.primary_location) | Select-Object -First 1
  if ($null -eq $location) { return $null }

  $countryCode = [string]$location.country_code
  if ([string]::IsNullOrWhiteSpace($countryCode)) { return $null }

  try {
    return [string]([System.Globalization.RegionInfo]::new($countryCode)).EnglishName
  } catch {
    return $countryCode.Trim().ToUpperInvariant()
  }
}

function Test-IsMultiselect {
  param([object]$Attribute)

  return (
    $Attribute.is_multiselect -eq $true -or
    $Attribute.config.is_multiselect -eq $true -or
    $Attribute.type -eq "multi-select"
  )
}

function Get-OptionMap {
  param([string]$AttributeSlug)

  $response = Invoke-AttioRequest -Method Get -Headers $devHeaders `
    -Path "/objects/$targetObjectSlug/attributes/$AttributeSlug/options"
  $map = @{}
  foreach ($option in @($response.data)) {
    if (-not $option.is_archived -and $option.id.option_id -and $option.title) {
      $map[$option.title.Trim().ToLowerInvariant()] = [string]$option.id.option_id
    }
  }
  return $map
}

function Convert-TargetValue {
  param(
    [string]$TargetSlug,
    [object[]]$Values,
    [hashtable]$TargetAttributes,
    [hashtable]$OptionMaps
  )

  if ($Values.Count -eq 0) {
    return $null
  }

  $attribute = $TargetAttributes[$TargetSlug]
  if ($TargetSlug -eq "domains" -or $TargetSlug -eq "email" -or $TargetSlug -eq "phone") {
    # Attio custom objects do not support domain/email/phone attributes or
    # multiselect text. Store a readable delimited value.
    $joinArray = @($Values | ForEach-Object { [string]$_ })
    return [string]($joinArray -join ", ")
  }
  if ($attribute.type -eq "currency") {
    return @{ currency_value = [decimal]$Values[0] }
  }
  if ($TargetSlug -eq "hq_country") {
    $location = $Values[0]
    if ($location -is [System.Collections.IDictionary]) {
      $countryCode = [string]$location["country_code"]
      if ([string]::IsNullOrWhiteSpace($countryCode)) {
        return $null
      }
      try {
        return ([System.Globalization.RegionInfo]::new($countryCode)).EnglishName
      } catch {
        return $countryCode
      }
    }
  }

  $converted = @()
  foreach ($value in $Values) {
    if ($attribute.type -eq "select") {
      $key = ([string]$value).Trim().ToLowerInvariant()
      if (-not $OptionMaps[$TargetSlug].ContainsKey($key)) {
        throw "Target option is missing for $TargetSlug`: '$value'."
      }
      $converted += $OptionMaps[$TargetSlug][$key]
    } else {
      $converted += $value
    }
  }

  if (Test-IsMultiselect -Attribute $attribute) {
    # Unary comma prevents PowerShell from unrolling a one-item array into a
    # scalar when the function returns through the pipeline.
    return ,@($converted)
  }
  if ($converted.Count -gt 1) {
    throw "Target $TargetSlug is single-value but SOURCE contains $($converted.Count) values: $($Values -join ', ')."
  }
  return $converted[0]
}

function Get-ExistingByLegacyId {
  param([string]$ObjectSlug = $targetObjectSlug)

  $map = @{}
  for ($offset = 0; ; $offset += $PageSize) {
    $response = Invoke-AttioRequest -Method Post -Headers $devHeaders `
      -Path "/objects/$ObjectSlug/records/query" `
      -Body @{ limit = $PageSize; offset = $offset }
    $records = @($response.data)
    foreach ($record in $records) {
      $legacyId = Get-SourceValues -Values $record.values -Slug "legacy_attio_id" |
        Select-Object -First 1
      if ($legacyId) {
        $map[[string]$legacyId] = Get-RecordId -Record $record
      }
    }
    if ($records.Count -lt $PageSize) { break }
  }
  return $map
}

$fieldMappings = if ($isPerson) {
  @(
    [pscustomobject]@{ Source = "name"; Target = "name" },
    [pscustomobject]@{ Source = "role"; Target = "role" },
    [pscustomobject]@{ Source = "email_addresses"; Target = "email" },
    [pscustomobject]@{ Source = "linkedin"; Target = "linkedin" },
    [pscustomobject]@{ Source = "relationship_status"; Target = "relationship_status" },
    [pscustomobject]@{ Source = "strongest_connection_strength"; Target = "connection_strength" },
    [pscustomobject]@{ Source = "last_interaction"; Target = "last_interaction_at" },
    [pscustomobject]@{ Source = "relationship_owner"; Target = "owner" },
    [pscustomobject]@{ Source = "job_title"; Target = "job_title" },
    [pscustomobject]@{ Source = "contact_type"; Target = "contact_type" },
    [pscustomobject]@{ Source = "phone_numbers"; Target = "phone" },
    [pscustomobject]@{ Source = "avatar_url"; Target = "avatar_url" },
    [pscustomobject]@{ Source = "angellist"; Target = "angellist" },
    [pscustomobject]@{ Source = "facebook"; Target = "facebook" },
    [pscustomobject]@{ Source = "instagram"; Target = "instagram" },
    [pscustomobject]@{ Source = "twitter"; Target = "twitter" },
    [pscustomobject]@{ Source = "twitter_follower_count"; Target = "twitter_follower_count" }
  )
} else {
  @(
    [pscustomobject]@{ Source = "name"; Target = "name" },
    [pscustomobject]@{ Source = "description"; Target = "description" },
    [pscustomobject]@{ Source = "type"; Target = "type" },
    [pscustomobject]@{ Source = "client_type"; Target = "client_type" },
    [pscustomobject]@{ Source = "sector_focus"; Target = "sector_focus" },
    [pscustomobject]@{ Source = "stage"; Target = "stage_focus" },
    [pscustomobject]@{ Source = "geographic_focus"; Target = "geographic_focus" },
    [pscustomobject]@{ Source = "primary_location"; Target = "hq_country" },
    [pscustomobject]@{ Source = "domains"; Target = "domains" },
    [pscustomobject]@{ Source = "logo_url"; Target = "logo_url" },
    [pscustomobject]@{ Source = "categories"; Target = "categories" },
    [pscustomobject]@{ Source = "relationship_status"; Target = "relationship_status" },
    [pscustomobject]@{ Source = "strongest_connection_strength"; Target = "connection_strength" },
    [pscustomobject]@{ Source = "last_interaction"; Target = "last_interaction_at" },
    [pscustomobject]@{ Source = "relationship_owner"; Target = "owner" },
    [pscustomobject]@{ Source = "funding_raised_usd"; Target = "funding_raised" },
    [pscustomobject]@{ Source = "estimated_arr_usd"; Target = "estimated_arr" },
    [pscustomobject]@{ Source = "angellist"; Target = "angellist" },
    [pscustomobject]@{ Source = "facebook"; Target = "facebook" },
    [pscustomobject]@{ Source = "instagram"; Target = "instagram" },
    [pscustomobject]@{ Source = "twitter"; Target = "twitter" },
    [pscustomobject]@{ Source = "twitter_follower_count"; Target = "twitter_follower_count" },
    [pscustomobject]@{ Source = "foundation_date"; Target = "foundation_date" },
    [pscustomobject]@{ Source = "ticket_size"; Target = "ticket_size" },
    [pscustomobject]@{ Source = "employee_range"; Target = "employee_range" },
    [pscustomobject]@{ Source = "linkedin"; Target = "linkedin" }
  )
}

Write-Host "Validating $entityName schema (SOURCE: $sourceObjectSlug; DEV custom target: $targetObjectSlug)."
$sourceAttributes = Get-AttributeMap -Headers $sourceHeaders -ObjectSlug $sourceObjectSlug
$targetAttributes = Get-AttributeMap -Headers $devHeaders -ObjectSlug $targetObjectSlug

$missingSource = @(
  $fieldMappings.Source |
    Where-Object { -not $sourceAttributes.ContainsKey($_) } |
    Sort-Object -Unique
)
$requiredTarget = @($fieldMappings.Target) + @("legacy_attio_id")
if ($isPerson) { $requiredTarget += "company" } else { $requiredTarget += "is_active" }
$missingTarget = @(
  $requiredTarget |
    Where-Object { -not $targetAttributes.ContainsKey($_) } |
    Sort-Object -Unique
)

if ($missingSource.Count -gt 0) {
  throw "SOURCE $entityName attributes are missing: $($missingSource -join ', '). Refresh discovery or correct the mapping."
}
if ($missingTarget.Count -gt 0) {
  throw "DEV $entityName attributes are missing: $($missingTarget -join ', '). Create the target schema before migrating records."
}

$optionMaps = @{}
foreach ($mapping in $fieldMappings) {
  if ($targetAttributes[$mapping.Target].type -eq "select" -and
      -not $optionMaps.ContainsKey($mapping.Target)) {
    $optionMaps[$mapping.Target] = Get-OptionMap -AttributeSlug $mapping.Target
  }
}

Write-Host "Indexing existing DEV $entityName records by legacy_attio_id."
$devByLegacyId = Get-ExistingByLegacyId -ObjectSlug $targetObjectSlug
$devOrganizationsByLegacyId = @{}
if ($isPerson) {
  Write-Host "Indexing DEV Organizations for Person company references."
  $devOrganizationsByLegacyId = Get-ExistingByLegacyId -ObjectSlug "organizations"
}

# is_active resolves SOURCE Organizations that share a name (case/whitespace
# insensitive): the newest by created_at is active, every older duplicate in
# the group is inactive. Requires the full SOURCE company set regardless of
# this run's -StartOffset/-Limit slice, since a duplicate pair can land in
# different offset windows (or different parallel workers).
$isActiveBySourceId = @{}
if (-not $isPerson) {
  Write-Host "Grouping SOURCE Organizations by name to resolve is_active."
  $allSourceCompanies = @()
  for ($groupOffset = 0; ; $groupOffset += $PageSize) {
    $groupResponse = Invoke-AttioRequest -Method Post -Headers $sourceHeaders `
      -Path "/objects/$sourceObjectSlug/records/query" `
      -Body @{ limit = $PageSize; offset = $groupOffset }
    $groupPage = @($groupResponse.data)
    $allSourceCompanies += $groupPage
    if ($groupPage.Count -lt $PageSize) { break }
  }
  $nameGroups = @{}
  foreach ($company in $allSourceCompanies) {
    $companyName = @(Get-SourceValues -Values $company.values -Slug "name") | Select-Object -First 1
    if (-not $companyName) { continue }
    $normalizedName = ([string]$companyName).Trim().ToLowerInvariant()
    if ([string]::IsNullOrWhiteSpace($normalizedName)) { continue }
    if (-not $nameGroups.ContainsKey($normalizedName)) {
      $nameGroups[$normalizedName] = [System.Collections.Generic.List[object]]::new()
    }
    $nameGroups[$normalizedName].Add($company)
  }
  foreach ($group in $nameGroups.Values) {
    $orderedGroup = @($group | Sort-Object { [datetime]$_.created_at } -Descending)
    for ($groupIndex = 0; $groupIndex -lt $orderedGroup.Count; $groupIndex++) {
      $isActiveBySourceId[(Get-RecordId -Record $orderedGroup[$groupIndex])] = ($groupIndex -eq 0)
    }
  }
  $duplicateNameGroups = @($nameGroups.Values | Where-Object Count -gt 1).Count
  Write-Host "Resolved is_active for $($isActiveBySourceId.Count) named Organizations ($duplicateNameGroups duplicate-name groups)."
}
$sourceRecords = @()
$offset = $StartOffset
while ($Limit -eq 0 -or $sourceRecords.Count -lt $Limit) {
  $queryLimit = $PageSize
  if ($Limit -gt 0) {
    $queryLimit = [Math]::Min($PageSize, $Limit - $sourceRecords.Count)
  }

  $sourceResponse = Invoke-AttioRequest -Method Post -Headers $sourceHeaders `
    -Path "/objects/$sourceObjectSlug/records/query" `
    -Body @{ limit = $queryLimit; offset = $offset }
  $page = @($sourceResponse.data)
  $sourceRecords += $page
  if ($page.Count -lt $queryLimit) { break }
  $offset += $page.Count
}

$stats = [ordered]@{
  inspected = 0
  would_create = 0
  would_update = 0
  created = 0
  updated = 0
  field_warnings = 0
  errors = 0
}

foreach ($record in $sourceRecords) {
  $stats.inspected++
  $sourceId = Get-RecordId -Record $record
  $payload = @{ legacy_attio_id = $sourceId }
  if (-not $isPerson) {
    # Every migrated Organization is historic-by-definition for this
    # migration, regardless of whether SOURCE had a real lead_source tool
    # name (Valuation Tool, M&A Readiness Tool, Buyer Form) or nothing at
    # all -- "Outbound" is reserved for organizations created going forward
    # via manual outreach, never written by this migration.
    $payload.lead_source = "Inbound"
    $payload.is_active = if ($isActiveBySourceId.ContainsKey($sourceId)) {
      $isActiveBySourceId[$sourceId]
    } else {
      $true
    }
  }
  $recordErrors = @()
  $recordWarnings = @()

  foreach ($mapping in $fieldMappings) {
    if ($mapping.Target -eq "hq_country") {
      $hqCountry = Get-HqCountry -Values $record.values
      if (-not [string]::IsNullOrWhiteSpace($hqCountry)) {
        $payload[$mapping.Target] = [string]$hqCountry
      }
      continue
    }

    if ($mapping.Target -eq "relationship_status") {
      try {
        $normalizedStatus = Get-NormalizedRelationshipStatus -Values $record.values
        if (-not [string]::IsNullOrWhiteSpace($normalizedStatus)) {
          $payload[$mapping.Target] = Convert-TargetValue `
            -TargetSlug $mapping.Target `
            -Values @($normalizedStatus) `
            -TargetAttributes $targetAttributes `
            -OptionMaps $optionMaps
        }
      } catch {
        $recordErrors += $_.Exception.Message
      }
      continue
    }

    if ($mapping.Target -eq "owner") {
      $ownerNames = @(Get-SourceValues -Values $record.values -Slug $mapping.Source)
      if ($ownerNames.Count -gt 1) {
        $recordWarnings += "owner: SOURCE relationship_owner has multiple values ($($ownerNames -join ', ')); using the first."
      }
      if ($ownerNames.Count -gt 0) {
        $ownerKey = ([string]$ownerNames[0]).Trim().ToLowerInvariant()
        if ($ownerCrosswalkByName.ContainsKey($ownerKey)) {
          $payload.owner = @{
            referenced_actor_type = "workspace-member"
            referenced_actor_id = $ownerCrosswalkByName[$ownerKey]
          }
        } else {
          $recordWarnings += "owner: no DEV workspace-member mapped for SOURCE relationship_owner '$($ownerNames[0])'."
        }
      }
      continue
    }

    $sourceValues = @(Get-SourceValues -Values $record.values -Slug $mapping.Source)
    if ($sourceValues.Count -eq 0) { continue }
    try {
      $payload[$mapping.Target] = Convert-TargetValue `
        -TargetSlug $mapping.Target `
        -Values $sourceValues `
        -TargetAttributes $targetAttributes `
        -OptionMaps $optionMaps
    } catch {
      if ($_.Exception.Message -match "^Target .+ is single-value but SOURCE contains") {
        $recordWarnings += "$($mapping.Target): $($_.Exception.Message)"
      } else {
        $recordErrors += $_.Exception.Message
      }
    }
  }

  if ($isPerson) {
    $sourceCompanyIds = @(Get-SourceReferenceIds `
      -Values $record.values -Slugs @("company", "company_4"))
    if ($sourceCompanyIds.Count -gt 1) {
      $recordWarnings += "company: SOURCE contains multiple company references; using the first."
    }
    if ($sourceCompanyIds.Count -gt 0) {
      $sourceCompanyId = [string]$sourceCompanyIds[0]
      if ($devOrganizationsByLegacyId.ContainsKey($sourceCompanyId)) {
        $payload.company = @{
          target_object = "organizations"
          target_record_id = $devOrganizationsByLegacyId[$sourceCompanyId]
        }
      } else {
        $recordWarnings += "company: no DEV Organization found for SOURCE company $sourceCompanyId."
      }
    }
  }

  # DEV requires a record label. Standard SOURCE Companies can display their
  # domain when the name is blank, so preserve that behavior for Organizations.
  # Use a deterministic placeholder only when neither name nor domain exists.
  if (-not $payload.ContainsKey("name") -or
      [string]::IsNullOrWhiteSpace([string]$payload.name)) {
    if ($isPerson -and $payload.ContainsKey("email") -and
        -not [string]::IsNullOrWhiteSpace([string]$payload.email)) {
      $payload.name = ([string]$payload.email -split ",")[0].Trim()
    } elseif ($isPerson) {
      $payload.name = "Unnamed person"
    } elseif ($payload.ContainsKey("domains") -and
        -not [string]::IsNullOrWhiteSpace([string]$payload.domains)) {
      $payload.name = ([string]$payload.domains -split ",")[0].Trim()
    } else {
      $payload.name = "Unnamed $entityName [$sourceId]"
    }
  }

  foreach ($mapping in $fieldMappings) {
    if (-not $payload.ContainsKey($mapping.Target)) { continue }
    if ($targetAttributes[$mapping.Target].type -eq "text" -and
        $payload[$mapping.Target] -isnot [string]) {
      $recordErrors += "Internal validation: $($mapping.Target) must serialize as text, received $($payload[$mapping.Target].GetType().FullName)."
      continue
    }
    if (-not (Test-IsMultiselect -Attribute $targetAttributes[$mapping.Target])) {
      continue
    }
    if ($payload[$mapping.Target] -isnot [array]) {
      $recordErrors += "Internal validation: $($mapping.Target) must serialize as an array."
    }
  }

  if ($recordErrors.Count -gt 0) {
    $stats.errors++
    Write-Warning "SOURCE $sourceId skipped: $($recordErrors -join ' | ')"
    continue
  }

  foreach ($warning in $recordWarnings) {
    $stats.field_warnings++
    Write-Warning "SOURCE $sourceId field omitted: $warning"
    Write-Output "FIELD_CONFLICT|$sourceId|$warning"
  }

  $exists = $devByLegacyId.ContainsKey($sourceId)
  if (-not $Apply) {
    if ($exists) {
      $stats.would_update++
      Write-Host "DRY RUN: would update $entityName $sourceId ($($payload.Count) fields)."
    } else {
      $stats.would_create++
      Write-Host "DRY RUN: would create $entityName $sourceId ($($payload.Count) fields)."
    }
    continue
  }

  try {
    if ($exists) {
      $devRecordId = $devByLegacyId[$sourceId]
      # PUT overwrites supplied multiselect values. PATCH would append them and
      # could duplicate selections when this idempotent migration is rerun.
      Invoke-AttioRequest -Method Put -Headers $devHeaders `
        -Path "/objects/$targetObjectSlug/records/$devRecordId" `
        -Body @{ data = @{ values = $payload } } | Out-Null
      $stats.updated++
      Write-Host "Updated $entityName $sourceId."
    } else {
      $created = Invoke-AttioRequest -Method Post -Headers $devHeaders `
        -Path "/objects/$targetObjectSlug/records" `
        -Body @{ data = @{ values = $payload } }
      $devByLegacyId[$sourceId] = Get-RecordId -Record $created.data
      $stats.created++
      Write-Host "Created $entityName $sourceId."
    }
  } catch {
    $message = if ($_.ErrorDetails.Message) {
      $_.ErrorDetails.Message
    } else {
      $_.Exception.Message
    }

    # Offset pagination can miss an existing record while parallel workers are
    # indexing DEV. Attio's unique legacy_attio_id constraint remains the
    # authority: recover the conflicting DEV record ID and update it instead
    # of treating the safe duplicate-create rejection as a terminal failure.
    if (-not $exists -and
        $message -match '"code"\s*:\s*"uniqueness_conflict"' -and
        $message -match 'Conflicting record IDs:\s*([0-9a-f-]{36})') {
      $conflictingRecordId = [string]$Matches[1]
      try {
        Invoke-AttioRequest -Method Put -Headers $devHeaders `
          -Path "/objects/$targetObjectSlug/records/$conflictingRecordId" `
          -Body @{ data = @{ values = $payload } } | Out-Null
        $devByLegacyId[$sourceId] = $conflictingRecordId
        $stats.updated++
        Write-Host "Recovered existing $entityName $sourceId after uniqueness conflict."
        continue
      } catch {
        $message = if ($_.ErrorDetails.Message) {
          $_.ErrorDetails.Message
        } else {
          $_.Exception.Message
        }
      }
    }

    $stats.errors++
    Write-Warning "SOURCE $sourceId failed: $message"
  }
}

Write-Host ""
if ($Apply) {
  Write-Host "$entityName apply complete."
} else {
  Write-Host "$entityName dry run complete. Add -Apply only after reviewing this output."
}
[pscustomobject]$stats | Format-List

if ($stats.errors -gt 0) {
  exit 1
}

}
function Invoke-ObjectParallel {
param(
  [ValidateSet("organizations", "person")]
  [string]$Object = "organizations",
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [string]$DevApiKey = $env:DEV_ATTIO_API_KEY,
  [ValidateRange(1, 8)]
  [int]$Workers = 4,
  [int]$PageSize = 500,
  [switch]$Apply
)


$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($SourceApiKey)) {
  throw "Missing SOURCE_ATTIO_API_KEY."
}
if ([string]::IsNullOrWhiteSpace($DevApiKey)) {
  throw "Missing DEV_ATTIO_API_KEY."
}

# Child PowerShell workers inherit these process-scoped values. Keys are not
# included in command-line arguments or logs.
$env:SOURCE_ATTIO_API_KEY = $SourceApiKey.Trim()
$env:DEV_ATTIO_API_KEY = $DevApiKey.Trim()

$sourceHeaders = @{
  Authorization = "Bearer $env:SOURCE_ATTIO_API_KEY"
  Accept = "application/json"
  "Content-Type" = "application/json"
}

function Invoke-AttioPost {
  param([string]$Path, [object]$Body)

  for ($attempt = 1; $attempt -le 8; $attempt++) {
    try {
      return Invoke-RestMethod `
        -Method Post `
        -Uri "https://api.attio.com/v2$Path" `
        -Headers $sourceHeaders `
        -Body ([System.Text.Encoding]::UTF8.GetBytes(
          ($Body | ConvertTo-Json -Depth 20)
        ))
    } catch {
      $statusCode = 0
      if ($_.Exception.Response) {
        $statusCode = [int]$_.Exception.Response.StatusCode
      }
      if ($attempt -eq 8 -or ($statusCode -ne 429 -and $statusCode -lt 500)) {
        throw
      }
      $delay = [Math]::Min(60, 5 * $attempt)
      Write-Warning "Count request returned HTTP $statusCode. Retrying in $delay seconds."
      Start-Sleep -Seconds $delay
    }
  }
}

$sourceObjectSlug = if ($Object -eq "person") { "people" } else { "companies" }
$entityName = if ($Object -eq "person") { "Person" } else { "Organization" }

Write-Host "Counting SOURCE $sourceObjectSlug."
$totalRecords = 0
for ($offset = 0; ; $offset += $PageSize) {
  $response = Invoke-AttioPost -Path "/objects/$sourceObjectSlug/records/query" `
    -Body @{ limit = $PageSize; offset = $offset }
  $page = @($response.data)
  $totalRecords += $page.Count
  Write-Host "Counted $totalRecords SOURCE $sourceObjectSlug."
  if ($page.Count -lt $PageSize) { break }
}

if ($totalRecords -eq 0) {
  throw "SOURCE contains no $sourceObjectSlug records."
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..\..\scripts")
$workerScript = Join-Path $PSScriptRoot "objects.ps1"
$mode = if ($Apply) { "apply" } else { "dry-run" }
$logDirectory = Join-Path $repoRoot "outputs\attio_migration\parallel-$Object\$mode"
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$conflictReport = Join-Path $logDirectory "field-conflicts.csv"
if (Test-Path -LiteralPath $conflictReport) {
  Remove-Item -LiteralPath $conflictReport -Force
}

$workerCount = [Math]::Min($Workers, $totalRecords)
$recordsPerWorker = [int][Math]::Ceiling($totalRecords / $workerCount)
$jobs = @()

Write-Host ""
Write-Host "SOURCE $sourceObjectSlug`: $totalRecords"
Write-Host "Workers: $workerCount"
Write-Host "Records per worker: up to $recordsPerWorker"
Write-Host "Mode: $mode"

for ($index = 0; $index -lt $workerCount; $index++) {
  $startOffset = $index * $recordsPerWorker
  $limit = [Math]::Min($recordsPerWorker, $totalRecords - $startOffset)
  if ($limit -le 0) { continue }

  $workerNumber = $index + 1
  $logFile = Join-Path $logDirectory "worker-$workerNumber-offset-$startOffset.log"
  $errorFile = Join-Path $logDirectory "worker-$workerNumber-offset-$startOffset.err.log"
  $arguments = @(
    "-ExecutionPolicy", "Bypass",
    "-File", $workerScript,
    "-Task", "record",
    "-Object", $Object,
    "-StartOffset", $startOffset,
    "-Limit", $limit,
    "-PageSize", ([Math]::Min(500, $PageSize))
  )
  if ($Apply) {
    $arguments += "-Apply"
  }

  Write-Host "Worker $workerNumber`: offset=$startOffset limit=$limit"
  $process = Start-Process `
    -FilePath "powershell" `
    -ArgumentList $arguments `
    -WorkingDirectory $repoRoot `
    -RedirectStandardOutput $logFile `
    -RedirectStandardError $errorFile `
    -PassThru `
    -WindowStyle Hidden

  $jobs += [pscustomobject]@{
    Worker = $workerNumber
    Offset = $startOffset
    Limit = $limit
    Process = $process
    Log = $logFile
    ErrorLog = $errorFile
  }
}

while (@($jobs | Where-Object { -not $_.Process.HasExited }).Count -gt 0) {
  $running = @($jobs | Where-Object { -not $_.Process.HasExited }).Count
  Write-Host "Workers still running: $running"
  Start-Sleep -Seconds 10
}

$failed = @()
$fieldConflicts = @()
foreach ($job in $jobs) {
  # WaitForExit populates ExitCode reliably on the Start-Process object.
  $job.Process.WaitForExit()
  $job.Process.Refresh()
  $errorText = if (Test-Path $job.ErrorLog) {
    Get-Content -Path $job.ErrorLog -Raw
  } else {
    ""
  }
  $logText = if (Test-Path $job.Log) {
    Get-Content -Path $job.Log -Raw
  } else {
    ""
  }
  $reportedZeroErrors = $logText -match "errors\s*:\s*0"
  $reportedComplete = $logText -match "$entityName (dry run|apply) complete"

  foreach ($line in @($logText -split "`r?`n")) {
    if ($line -match "^FIELD_CONFLICT\|([0-9a-f-]{36})\|([^:]+):\s+(.+)$") {
      $fieldConflicts += [pscustomobject]@{
        worker = $job.Worker
        source_record_id = $Matches[1]
        field = $Matches[2].Trim()
        detail = $Matches[3].Trim()
      }
    }
  }

  # Windows PowerShell can return an unavailable/stale ExitCode for a process
  # launched with redirected output. Treat the worker's completion marker,
  # zero-error summary, and empty stderr as the authoritative result.
  if (-not [string]::IsNullOrWhiteSpace($errorText) -or
      -not $reportedComplete -or
      -not $reportedZeroErrors) {
    $failed += $job
  }
}

if ($fieldConflicts.Count -gt 0) {
  $fieldConflicts |
    Sort-Object source_record_id, field |
    Export-Csv -Path $conflictReport -NoTypeInformation -Encoding UTF8
  Write-Warning "$($fieldConflicts.Count) field conflict(s) were omitted and written to $conflictReport."
}

if ($failed.Count -gt 0) {
  Write-Warning "$($failed.Count) $entityName worker(s) failed."
  $failed | Select-Object Worker, Offset, Limit, Log, ErrorLog | Format-Table -AutoSize
  Write-Host "Review logs under $logDirectory."
  exit 1
}

Write-Host ""
Write-Host "Parallel $entityName $mode complete with zero worker errors."
Write-Host "Logs: $logDirectory"

}
function Invoke-Deals {
param(
  [string]$SourceApiKey=$env:SOURCE_ATTIO_API_KEY,
  [string]$DevApiKey=$env:DEV_ATTIO_API_KEY,
  [string]$DevOwnerWorkspaceMemberId,
  [int]$Limit=0,
  [string]$Confirmation,
  [switch]$ExistingOnly,
  [switch]$DeleteOrphaned,
  [switch]$MigrateMandates,
  [switch]$Apply
)

$ErrorActionPreference="Stop"
if([string]::IsNullOrWhiteSpace($SourceApiKey)){$SourceApiKey=[Environment]::GetEnvironmentVariable("SOURCE_ATTIO_API_KEY","User")}
if([string]::IsNullOrWhiteSpace($DevApiKey)){$DevApiKey=[Environment]::GetEnvironmentVariable("DEV_ATTIO_API_KEY","User")}
if([string]::IsNullOrWhiteSpace($SourceApiKey)){throw "Missing SOURCE_ATTIO_API_KEY."}
if([string]::IsNullOrWhiteSpace($DevApiKey)){throw "Missing DEV_ATTIO_API_KEY."}
if($Apply){
  if($DeleteOrphaned){
    if($Confirmation-ne"DELETE_ORPHANED_DEALS_FROM_DEV"){throw "Apply with -DeleteOrphaned requires -Confirmation DELETE_ORPHANED_DEALS_FROM_DEV."}
  }else{
    $bounded=$Limit-ge1-and$Limit-le10-and$Confirmation-eq"APPLY_DEALS_TO_DEV"
    $full=$Limit-eq0-and$Confirmation-eq"APPLY_ALL_DEALS_TO_DEV"
    if(-not$bounded-and-not$full){throw "Use a 1-10 limit with APPLY_DEALS_TO_DEV, or Limit 0 with APPLY_ALL_DEALS_TO_DEV."}
  }
}
$sh=@{Authorization="Bearer $($SourceApiKey.Trim())";Accept="application/json";"Content-Type"="application/json"}
$dh=@{Authorization="Bearer $($DevApiKey.Trim())";Accept="application/json";"Content-Type"="application/json"}
$decisions=Get-Content (Join-Path $PSScriptRoot "..\config\migration-decisions.json") -Raw|ConvertFrom-Json
$expectedWorkspaceId=[string]$decisions.dev_workspace_id
# Deal.owner was previously never read from SOURCE at all -- every DEV Deal
# got the same hardcoded batch default (Tech Wusool) at creation and was
# never touched again on update. Keyed by SOURCE workspace-member ID (not
# name) since SOURCE Deal owner is a real actor-reference, unlike
# Organization/Person's relationship_owner select field. Two of the five
# SOURCE deal owners are deactivated former members with no name recoverable
# via the API; those stay unresolved and fall back to the existing default.
$ownerCrosswalkBySourceId=@{}
foreach($entry in @($decisions.workspace_member_crosswalk.mapping)){
  $sourceId=[string]$entry.source_workspace_member_id
  if(-not[string]::IsNullOrWhiteSpace($sourceId)){$ownerCrosswalkBySourceId[$sourceId]=[string]$entry.dev_workspace_member_id}
}
# Blank-duplicate SOURCE companies (a second lead-magnet submission for a
# company that already exists) that were never migrated into DEV
# Organizations and so block seller resolution below. SOURCE is read-only
# to this tooling, so the duplicate can't be repointed at the source --
# instead it's aliased here to the real, already-migrated SOURCE company id.
$duplicateCompanyAlias=@{}
if($decisions.duplicate_source_company_ids.mapping){
  foreach($property in $decisions.duplicate_source_company_ids.mapping.PSObject.Properties){
    $duplicateCompanyAlias[[string]$property.Name]=[string]$property.Value
  }
}
$outputPath=Join-Path $PSScriptRoot "..\..\..\..\scripts\outputs\attio_migration\deals-plan.json"
function Request{
  param([ValidateSet("Get","Post","Put","Delete")][string]$Method,[hashtable]$Headers,[string]$Path,[object]$Body)
  $p=@{Method=$Method;Uri="https://api.attio.com/v2$Path";Headers=$Headers}
  if($null-ne$Body){$p.Body=[Text.Encoding]::UTF8.GetBytes(($Body|ConvertTo-Json -Depth 30))}
  Invoke-RestMethod @p
}
function All($headers,$path){$all=@();for($o=0;;$o+=500){$p=@((Request Post $headers $path @{limit=500;offset=$o}).data);$all+=$p;if($p.Count-lt500){break}};return $all}
function Id($r){if($r.id.record_id){return [string]$r.id.record_id};return [string]$r.record_id}
function ReferenceId($vs,$slug){
  $x=@($vs.$slug)|Where-Object{$null-eq$_.active_until}|Select-Object -First 1
  if($null-eq$x-or-not$x.target_record_id){return $null}
  return [string]$x.target_record_id
}
function ActiveValue($vs,$slug){
  return @($vs.$slug)|Where-Object{$null-eq$_.active_until}|Select-Object -First 1
}
function Value($vs,$slug){
  $x=ActiveValue $vs $slug
  if($null-eq$x){return $null}
  if($null-ne$x.value){return $x.value}
  if($x.status.title){return [string]$x.status.title}
  if($x.option.title){return [string]$x.option.title}
  if($null-ne$x.currency_value){return $x.currency_value}
  return $null
}
function Values($vs,$slug){
  return @(@($vs.$slug)|Where-Object{$null-eq$_.active_until}|ForEach-Object{if($_.option.title){[string]$_.option.title}}|Where-Object{-not[string]::IsNullOrWhiteSpace($_)})
}
function CheckboxValue($vs,$slug){
  $x=ActiveValue $vs $slug
  if($null-eq$x-or$null-eq$x.value){return $null}
  return [bool]$x.value
}
function MoneyValue($vs,$slug){
  $x=@($vs.$slug)|Where-Object{$null-eq$_.active_until}|Select-Object -First 1
  if($null-eq$x-or$null-eq$x.currency_value){return $null}
  # NOT converted to USD, unlike the other AED fields in this AED->USD
  # cleanup (2026-08-25): "value" is Attio's built-in System attribute on
  # Deals, and Attio rejects any config change on System attributes (confirmed
  # live: HTTP 400 system_edit_unauthorized on both "title" and "config").
  # Its currency is permanently stuck at AED, so converting the number here
  # would produce a wrong figure under a label that can never change to match.
  if([string]$x.currency_code-ne"AED"){throw "Unexpected SOURCE Deal currency '$($x.currency_code)'; DEV Deal value is configured for AED."}
  return @{currency_value=[decimal]$x.currency_value}
}
$devObject=Request Get $dh "/objects/deals" $null
$workspaceId=[string]$devObject.data.id.workspace_id
if($workspaceId-ne$expectedWorkspaceId){throw "DEV workspace mismatch. Expected $expectedWorkspaceId but connected to $workspaceId."}
$source=@(All $sh "/objects/deals/records/query")
$dev=@(All $dh "/objects/deals/records/query")
if($DeleteOrphaned){
  # Idempotency here only ever meant "safe to re-run the create/update loop
  # below" -- it never covered the reverse direction (a SOURCE Deal deleted
  # after migration leaves an orphaned DEV Deal behind forever, since the
  # loop below only ever creates/updates, matched by legacy_attio_id, and
  # never looks at DEV records the SOURCE side no longer has). A DEV Deal
  # with no legacy_attio_id at all is a legitimate DEV-native record (e.g.
  # created directly by the lead-magnet automation) and must never be
  # touched here -- only ones that WERE migrated from a SOURCE id that has
  # since vanished are orphans.
  $sourceIdSet=@{}
  foreach($s in $source){$sourceIdSet[(Id $s)]=$true}
  $orphans=@($dev|Where-Object{
    $legacy=Value $_.values "legacy_attio_id"
    $legacy-and-not$sourceIdSet.ContainsKey([string]$legacy)
  })
  Write-Host "DEV Deals total: $($dev.Count)"
  Write-Host "SOURCE Deals total: $($source.Count)"
  Write-Host "Orphaned (legacy_attio_id no longer present in SOURCE): $($orphans.Count)"
  Write-Host ""
  $deleted=0;$errors=0
  foreach($o in $orphans){
    $name=Value $o.values "name"
    $recordId=Id $o
    $legacy=Value $o.values "legacy_attio_id"
    if($Apply){
      try{
        Request Delete $dh "/objects/deals/records/$recordId" $null|Out-Null
        Write-Host "Deleted: $name ($recordId)"
        $deleted++
      }catch{
        Write-Warning "FAILED to delete $name ($recordId): $($_.Exception.Message)"
        $errors++
      }
    }else{
      Write-Host "Would delete: $name ($recordId) -- legacy_attio_id=$legacy not found in SOURCE"
    }
  }
  Write-Host ""
  if($Apply){Write-Host "Done. Deleted $deleted, failed $errors."}else{Write-Host "Dry run only -- no records were deleted. Re-run with -Apply -Confirmation DELETE_ORPHANED_DEALS_FROM_DEV to delete."}
  return
}
$devOrganizations=@(All $dh "/objects/organizations/records/query")
$organizationByLegacy=@{}
foreach($r in $devOrganizations){
  $legacy=Value $r.values "legacy_attio_id"
  if(-not$legacy){continue}
  if($organizationByLegacy.ContainsKey([string]$legacy)){throw "Duplicate DEV Organization legacy_attio_id '$legacy'."}
  $organizationByLegacy[[string]$legacy]=Id $r
}
$byLegacy=@{}
foreach($r in $dev){$legacy=Value $r.values "legacy_attio_id";if($legacy){if($byLegacy.ContainsKey([string]$legacy)){throw "Duplicate DEV Deal legacy_attio_id."};$byLegacy[[string]$legacy]=$r}}

$statusMap=@{}
foreach($x in @((Request Get $dh "/objects/deals/attributes/stage/statuses" $null).data|Where-Object{-not$_.is_archived})){$statusMap[[string]$x.title]=[string]$x.id.status_id}
$teaserMap=@{}
foreach($x in @((Request Get $dh "/objects/deals/attributes/teaser_status/options" $null).data|Where-Object{-not$_.is_archived})){$teaserMap[[string]$x.title]=[string]$x.id.option_id}
$ndaStatusMap=@{}
foreach($x in @((Request Get $dh "/objects/deals/attributes/nda_status/options" $null).data|Where-Object{-not$_.is_archived})){$ndaStatusMap[[string]$x.title]=[string]$x.id.option_id}
$advisorMap=@{}
foreach($x in @((Request Get $dh "/objects/deals/attributes/assigned_advisor/options" $null).data|Where-Object{-not$_.is_archived})){$advisorMap[[string]$x.title]=[string]$x.id.option_id}
$plans=[Collections.Generic.List[object]]::new()
foreach($s in $source){
  $sid=Id $s
  $existing=if($byLegacy.ContainsKey($sid)){$byLegacy[$sid]}else{$null}
  $action=if($null-ne$existing){"update"}else{"create"}
  $name=Value $s.values "name";if([string]::IsNullOrWhiteSpace([string]$name)){$name="Unknown Source Deal $sid"}
  $values=@{legacy_attio_id=$sid;name=[string]$name}
  $sourceOwnerItem=ActiveValue $s.values "owner"
  $sourceOwnerId=if($sourceOwnerItem){[string]$sourceOwnerItem.referenced_actor_id}else{$null}
  $resolvedOwnerId=if($sourceOwnerId-and$ownerCrosswalkBySourceId.ContainsKey($sourceOwnerId)){$ownerCrosswalkBySourceId[$sourceOwnerId]}else{$null}
  $ownerResolution=if(-not$sourceOwnerId){"missing_source_owner"}elseif($resolvedOwnerId){"resolved"}else{"unmapped_source_owner"}
  if($resolvedOwnerId){$values.owner=@{referenced_actor_type="workspace-member";referenced_actor_id=$resolvedOwnerId}}
  $sourceStageValue=ActiveValue $s.values "stage"
  $stage=Value $s.values "stage";if($stage){$values.stage=[string]$stage}
  if($action-eq"update"-and$stage){
    $devStage=Value $existing.values "stage"
    $devStageChangedAt=Value $existing.values "stage_changed_at"
    if($devStage-and[string]$devStage-ne[string]$stage){
      $changedAt=if($sourceStageValue.active_from){[string]$sourceStageValue.active_from}else{[DateTime]::UtcNow.ToString("o")}
      $values.stage_changed_at=$changedAt
      $values.time_in_stage=0
    }elseif($devStageChangedAt){
      $elapsed=[DateTime]::UtcNow-([DateTime]::Parse([string]$devStageChangedAt).ToUniversalTime())
      $values.time_in_stage=[Math]::Round([Math]::Max(0,$elapsed.TotalDays),2)
    }
  }
  $value=MoneyValue $s.values "value";if($null-ne$value){$values.value=$value}
  $teaser=Value $s.values "teaser_status";if($teaser){$values.teaser_status=[string]$teaser}
  $nda=Value $s.values "ndas_signed_count";if($null-ne$nda){$values.nda_count=$nda}
  $cimStatus=Value $s.values "cim_status"
  if($cimStatus){$values.cim_ready=@("Approved","Distributed")-contains[string]$cimStatus}
  $memoFiled=CheckboxValue $s.values "deal_memo_filed"
  if($null-ne$memoFiled){
    $values.deal_memo_ready=$memoFiled
  }else{
    $memoDecision=Value $s.values "deal_memo_decision"
    if($memoDecision){$values.deal_memo_ready=@("Proceed","Pass")-contains[string]$memoDecision}
  }
  $exclusivityStart=Value $s.values "exclusivity_start_date";if($exclusivityStart){$values.contract_signed_date=[string]$exclusivityStart}
  $exclusivityEnd=Value $s.values "exclusivity_end_date";if($exclusivityEnd){$values.exclusivity_date=[string]$exclusivityEnd}
  $ndaStatus=Value $s.values "nda_status";if($ndaStatus){$values.nda_status=[string]$ndaStatus}
  # SOURCE's estimated_deal_value_aed is a real AED figure; DEV's renamed
  # estimated_deal_value_usd now expects USD (2026-08-25 cleanup) -- divide
  # by the fixed peg (1 USD = 3.6725 AED) instead of copying the raw number,
  # same conversion as lists.ps1's Add-EntryScalar -AedToUsd.
  $estDealValue=Value $s.values "estimated_deal_value_aed";if($null-ne$estDealValue){$values.estimated_deal_value_usd=[Math]::Round([decimal]$estDealValue/[decimal]3.6725,2)}
  $expectedClose=Value $s.values "expected_close_date";if($expectedClose){$values.expected_close_date=[string]$expectedClose}
  $fee=Value $s.values "fee";if($null-ne$fee){$values.fee=$fee}
  $advisorNames=@(Values $s.values "assigned_advisor")
  if($advisorNames.Count-gt0){$values.assigned_advisor=@($advisorNames)}
  $sourceSellerId=ReferenceId $s.values "associated_company"
  if($sourceSellerId-and$duplicateCompanyAlias.ContainsKey($sourceSellerId)){$sourceSellerId=$duplicateCompanyAlias[$sourceSellerId]}
  $sellerResolution="missing_source_associated_company"
  if($sourceSellerId-and$organizationByLegacy.ContainsKey($sourceSellerId)){
    $values.seller_id=@{target_object="organizations";target_record_id=$organizationByLegacy[$sourceSellerId]}
    $sellerResolution="resolved"
  }elseif($sourceSellerId){
    $sellerResolution="missing_dev_organization"
  }
  $plans.Add([pscustomobject]@{
    source_id=$sid
    source_seller_id=$sourceSellerId
    seller_resolution=$sellerResolution
    seller_org_id=if($sellerResolution-eq"resolved"){$organizationByLegacy[$sourceSellerId]}else{$null}
    dev_record_id=if($existing){Id $existing}else{$null}
    action=$action
    owner_resolution=$ownerResolution
    values=$values
  })
}
$unresolvedSellers=@($plans|Where-Object seller_resolution -eq "missing_dev_organization")
if($unresolvedSellers.Count-gt0){
  throw "Cannot migrate Deals: $($unresolvedSellers.Count) seller relationship(s) did not resolve uniquely to DEV Organizations."
}
$blankSellerDeals=@($plans|Where-Object seller_resolution -eq "missing_source_associated_company")
foreach($blankPlan in $blankSellerDeals){
  Write-Warning "Deal $($blankPlan.source_id) has no SOURCE seller company linked; migrating with seller_id left blank (matches SOURCE)."
}
$populatedDevBuyers=@($dev|Where-Object{(Value $_.values "legacy_attio_id")-and@($_.values.buyer_id|Where-Object{$null-eq$_.active_until}).Count-gt0})
if($populatedDevBuyers.Count-gt0){
  throw "Confirmed migration rule requires blank buyer_id on SOURCE-migrated Deals, but $($populatedDevBuyers.Count) such DEV Deal(s) are populated. Review before applying."
}
$eligiblePlans=if($ExistingOnly){@($plans|Where-Object action -eq "update")}else{@($plans)}
$selected=if($Limit-eq0){@($eligiblePlans)}else{@($eligiblePlans|Select-Object -First $Limit)}
$selectedCreates=@($selected|Where-Object action -eq "create")
$selectedCreatesNeedingOwner=@($selectedCreates|Where-Object{-not$_.values.ContainsKey("owner")})
if($Apply-and$selectedCreatesNeedingOwner.Count-gt0-and[string]::IsNullOrWhiteSpace($DevOwnerWorkspaceMemberId)){
  throw "Attio requires Deal owner. $($selectedCreatesNeedingOwner.Count) new Deal(s) have no resolvable SOURCE owner -- supply an approved DevOwnerWorkspaceMemberId as a fallback, or use -ExistingOnly."
}
$created=0;$updated=0;$errors=0
if($Apply){
  foreach($plan in $selected){
    $payload=@{};foreach($k in $plan.values.Keys){$payload[$k]=$plan.values[$k]}
    if($payload.ContainsKey("stage")){$title=[string]$payload.stage;if(-not$statusMap.ContainsKey($title)){throw "Missing DEV Deal stage '$title'."};$payload.stage=$statusMap[$title]}
    if($payload.ContainsKey("teaser_status")){$title=[string]$payload.teaser_status;if(-not$teaserMap.ContainsKey($title)){throw "Missing DEV teaser_status option '$title'."};$payload.teaser_status=$teaserMap[$title]}
    if($payload.ContainsKey("nda_status")){$title=[string]$payload.nda_status;if(-not$ndaStatusMap.ContainsKey($title)){throw "Missing DEV nda_status option '$title'."};$payload.nda_status=$ndaStatusMap[$title]}
    if($payload.ContainsKey("assigned_advisor")){
      $ids=[Collections.Generic.List[string]]::new()
      foreach($advisorTitle in @($payload.assigned_advisor)){
        if(-not$advisorMap.ContainsKey([string]$advisorTitle)){throw "Missing DEV assigned_advisor option '$advisorTitle'."}
        $ids.Add($advisorMap[[string]$advisorTitle])
      }
      $payload.assigned_advisor=@($ids)
    }
    if(-not$payload.ContainsKey("owner")-and$plan.action-eq"create"){$payload.owner=@{referenced_actor_type="workspace-member";referenced_actor_id=$DevOwnerWorkspaceMemberId}}
    try{
      if($plan.action-eq"update"){Request Put $dh "/objects/deals/records/$($plan.dev_record_id)" @{data=@{values=$payload}}|Out-Null;$updated++}
      else{$new=Request Post $dh "/objects/deals/records" @{data=@{values=$payload}};$plan.dev_record_id=Id $new.data;$created++}
    }catch{$errors++;throw}
  }
}
$summary=[ordered]@{mode=if($Apply){"apply"}else{"dry-run"};existing_only=[bool]$ExistingOnly;source_deals=$source.Count;existing_dev_deals=$dev.Count;resolved_existing=@($plans|Where-Object action -eq "update").Count;resolved_sellers=@($plans|Where-Object seller_resolution -eq "resolved").Count;unresolved_sellers=$unresolvedSellers.Count;resolved_owners=@($plans|Where-Object owner_resolution -eq "resolved").Count;unmapped_source_owners=@($plans|Where-Object owner_resolution -eq "unmapped_source_owner").Count;missing_source_owners=@($plans|Where-Object owner_resolution -eq "missing_source_owner").Count;populated_dev_buyers=$populatedDevBuyers.Count;would_create=@($plans|Where-Object action -eq "create").Count;owner_blocked_creates=$selectedCreatesNeedingOwner.Count;selected=$selected.Count;created=$created;updated=$updated;errors=$errors}
[IO.Directory]::CreateDirectory((Split-Path $outputPath -Parent))|Out-Null
[IO.File]::WriteAllText($outputPath,([ordered]@{summary=$summary;plans=@($plans)}|ConvertTo-Json -Depth 30),[Text.UTF8Encoding]::new($false))
$summary|Format-List
Write-Host "Deal plan written to $outputPath"
if(-not$Apply){Write-Host "No Attio records were written."}

if($MigrateMandates){
  Write-Host ""
  Write-Host "===== migrate mandates to deals ====="
  # 2026-08-23 Mandate/Deal merge (see migration-decisions.json): the
  # Mandates list is being retired -- every Mandate entry becomes its own
  # Deal record at the new "Mandate Active" stage (a signed mandate still
  # sourcing candidates, no specific counterparty locked in yet -- distinct
  # from "Mandate Signed", which already implies a specific counterparty and
  # signed terms). Requires ensure-schema.ps1 -Entities deals -Apply to have
  # run first (adds the merged fields + Mandate Active stage + deal_type
  # options). Idempotent via source_mandate_entry_id: safe to re-run,
  # already-migrated entries are skipped.
  #
  # Hardcoded rather than derived from workspace_member_crosswalk: several
  # crosswalk entries (Hugo, Tech Wusool, ValuationTool, n8n Integration)
  # all collapse onto the same DEV id (tech@) today, so a generic
  # "first word of source_name" derivation would be ambiguous/order
  # -dependent. Only these two real people are actually distinguishable DEV
  # identities right now.
  $advisorNameByDevId=@{
    "20ee7570-f1c0-476a-b505-c50e95d7c577"="Jules"  # Sinan Muhammed, DEV stand-in
    "67fb42ec-facb-40ab-bc37-7cc654a53d75"="Ramzy"  # Richu Cherian, DEV stand-in
  }
  $mandateOwnerWorkspaceMemberId="20ee7570-f1c0-476a-b505-c50e95d7c577"  # Sinan (Jules stand-in) -- common advisor across both mandates

  $mandateActiveStatusId=$statusMap["Mandate Active"]
  if(-not$mandateActiveStatusId){throw "Deal stage 'Mandate Active' not found -- run ensure-schema.ps1 -Entities deals -Apply first."}
  function OptionMap($path){$m=@{};foreach($o in @((Request Get $dh $path $null).data|Where-Object{-not$_.is_archived})){$m[[string]$o.title]=[string]$o.id.option_id};return $m}
  $dealTypeOptions=OptionMap "/objects/deals/attributes/deal_type/options"
  $mandateAdvisorOptions=OptionMap "/objects/deals/attributes/assigned_advisor/options"

  # Backfill deal_type=Sell-side on every pre-existing Deal that has a
  # seller_id but no deal_type yet. Confirmed against SOURCE, not assumed:
  # SOURCE deals has no buyer-referencing attribute at all (checked its full
  # attribute list) -- only associated_company (-> seller_id), so every Deal
  # ever migrated from SOURCE is sell-side by construction. Buy-side never
  # existed as a concept there; it only existed on the now-merged Mandate
  # list. Confirmed zero overlap too: none of the 58 SOURCE deal seller
  # companies appear in SOURCE buyer_brain (Buyer Role) either.
  Write-Host ""
  Write-Host "-- backfill deal_type=Sell-side on pre-existing Deals with seller_id set --"
  if(-not$dealTypeOptions.ContainsKey("Sell-side")){throw "Missing deal_type option 'Sell-side'."}
  $sellSideOptionId=$dealTypeOptions["Sell-side"]
  $sellSideCandidates=@($dev|Where-Object{
    $hasSeller=@($_.values.seller_id|Where-Object{$null-eq$_.active_until}).Count-gt0
    $hasDealType=@($_.values.deal_type|Where-Object{$null-eq$_.active_until}).Count-gt0
    $hasSeller-and-not$hasDealType
  })
  Write-Host "Candidates: $($sellSideCandidates.Count)"
  $sellSideBackfilled=0
  foreach($d in $sellSideCandidates){
    $name=Value $d.values "name"
    $recordId=Id $d
    if($Apply){
      Request Put $dh "/objects/deals/records/$recordId" @{data=@{values=@{deal_type=$sellSideOptionId}}}|Out-Null
      Write-Host "Backfilled Sell-side: $name ($recordId)"
      $sellSideBackfilled++
    }else{Write-Host "Would backfill Sell-side: $name ($recordId)"}
  }
  if($Apply){Write-Host "Backfilled $sellSideBackfilled."}else{Write-Host "Dry run only -- no records were written."}

  $migratedMandateIds=@{}
  foreach($d in $dev){
    $v=Value $d.values "source_mandate_entry_id"
    if($v){$migratedMandateIds[[string]$v]=$true}
  }
  $mandateEntries=@(All $dh "/lists/mandates/entries/query")
  $mandatesCreated=0;$mandatesSkipped=0
  foreach($entry in $mandateEntries){
    $mandateEntryId=[string]$entry.id.entry_id
    if($migratedMandateIds.ContainsKey($mandateEntryId)){Write-Host "SKIP (already migrated): entry $mandateEntryId";$mandatesSkipped++;continue}
    $orgId=[string]$entry.parent_record_id
    $orgName=(Request Get $dh "/objects/organizations/records/$orgId" $null).data.values.name[0].value
    $side=(ActiveValue $entry.entry_values "side").option.title
    $dealType=if($side-eq"buy"){"Buy-side"}else{"Sell-side"}
    $advisorActorIds=@($entry.entry_values.assigned_advisor|Where-Object{$null-eq$_.active_until}|ForEach-Object{[string]$_.referenced_actor_id})
    $advisorNames=@($advisorActorIds|ForEach-Object{$advisorNameByDevId[$_]}|Where-Object{$_})
    $universeConstructed=(ActiveValue $entry.entry_values "universe_constructed").value
    $universeSize=(ActiveValue $entry.entry_values "universe_size").value
    $shortlistApproved=(ActiveValue $entry.entry_values "shortlist_approved").value
    $shortlistSize=(ActiveValue $entry.entry_values "shortlist_size").value
    $tier1Contacted=(ActiveValue $entry.entry_values "tier1_contacted").value
    $mandateResponses=(ActiveValue $entry.entry_values "responses").value
    $retainer=ActiveValue $entry.entry_values "retainer_amount"

    $mValues=@{
      name="$orgName"
      stage=$mandateActiveStatusId
      source_mandate_entry_id=$mandateEntryId
      owner=@{referenced_actor_type="workspace-member";referenced_actor_id=$mandateOwnerWorkspaceMemberId}
      buyer_id=@{target_object="organizations";target_record_id=$orgId}
    }
    if(-not$dealTypeOptions.ContainsKey($dealType)){throw "Missing deal_type option '$dealType'."}
    $mValues.deal_type=$dealTypeOptions[$dealType]
    if($advisorNames.Count-gt0){
      $mIds=@($advisorNames|ForEach-Object{if(-not$mandateAdvisorOptions.ContainsKey($_)){throw "Missing assigned_advisor option '$_'."};$mandateAdvisorOptions[$_]})
      $mValues.assigned_advisor=$mIds
    }
    if($null-ne$universeConstructed){$mValues.universe_constructed=[bool]$universeConstructed}
    if($null-ne$universeSize){$mValues.universe_size=$universeSize}
    if($null-ne$shortlistApproved){$mValues.shortlist_approved=[bool]$shortlistApproved}
    if($null-ne$shortlistSize){$mValues.shortlist_size=$shortlistSize}
    if($null-ne$tier1Contacted){$mValues.tier1_contacted=$tier1Contacted}
    if($null-ne$mandateResponses){$mValues.responses=$mandateResponses}
    if($retainer-and$null-ne$retainer.currency_value){$mValues.retainer_amount=@{currency_value=[decimal]$retainer.currency_value}}

    Write-Host ""
    Write-Host "Deal: $orgName"
    Write-Host "  deal_type=$dealType advisor=$($advisorNames -join ',') owner=Sinan universe=$universeSize shortlist=$shortlistSize tier1_contacted=$tier1Contacted responses=$mandateResponses"
    if($Apply){
      $newDeal=Request Post $dh "/objects/deals/records" @{data=@{values=$mValues}}
      Write-Host "  CREATED: $($newDeal.data.id.record_id)"
      $mandatesCreated++
    }else{Write-Host "  Would create."}
  }
  Write-Host ""
  if($Apply){Write-Host "Mandate migration done. Created $mandatesCreated, skipped $mandatesSkipped (already migrated)."}
  else{Write-Host "Mandate migration dry run only -- no records were created."}
}

}
switch($Task){
 "record"{$a=@{Object=$Object;SourceApiKey=$SourceApiKey;DevApiKey=$DevApiKey;Limit=$Limit;StartOffset=$StartOffset;PageSize=$PageSize};if($Apply){$a.Apply=$true};Invoke-ObjectRecord @a}
 "parallel"{$a=@{Object=$Object;SourceApiKey=$SourceApiKey;DevApiKey=$DevApiKey;Workers=$Workers;PageSize=$PageSize};if($Apply){$a.Apply=$true};Invoke-ObjectParallel @a}
 "deals"{$a=@{SourceApiKey=$SourceApiKey;DevApiKey=$DevApiKey;Limit=$Limit;Confirmation=$Confirmation};if($DevOwnerWorkspaceMemberId){$a.DevOwnerWorkspaceMemberId=$DevOwnerWorkspaceMemberId};if($ExistingOnly){$a.ExistingOnly=$true};if($DeleteOrphaned){$a.DeleteOrphaned=$true};if($MigrateMandates){$a.MigrateMandates=$true};if($Apply){$a.Apply=$true};Invoke-Deals @a}
}
