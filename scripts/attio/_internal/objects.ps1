param(
 [ValidateSet("record","parallel","deals")][string]$Task,
 [ValidateSet("organizations","person")][string]$Object="organizations",
 [string]$SourceApiKey=$env:SOURCE_ATTIO_API_KEY,[string]$DevApiKey=$env:DEV_ATTIO_API_KEY,
 [int]$Limit=10,[int]$StartOffset=0,[int]$PageSize=100,[int]$Workers=4,
 [string]$DevOwnerWorkspaceMemberId,[string]$Confirmation,[switch]$ExistingOnly,[switch]$Apply
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
  if ($Item.full_name) { return [string]$Item.full_name }
  if ($Item.email_address) { return [string]$Item.email_address }
  if ($Item.option.title) { return [string]$Item.option.title }
  if ($Item.status.title) { return [string]$Item.status.title }
  if ($Item.domain) { return [string]$Item.domain }
  if ($Item.title) { return [string]$Item.title }
  if ($Item.country) { return [string]$Item.country }
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
  if ($TargetSlug -eq "domains" -or $TargetSlug -eq "email") {
    # Attio custom objects do not support domain attributes or multiselect text.
    # Store a readable delimited value; domain names cannot contain commas.
    $domainArray = @($Values | ForEach-Object { [string]$_ })
    return [string]($domainArray -join ", ")
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
    [pscustomobject]@{ Source = "last_interaction"; Target = "last_interaction_at" }
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
    [pscustomobject]@{ Source = "last_interaction"; Target = "last_interaction_at" }
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
if ($isPerson) { $requiredTarget += "company" }
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

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
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
  [switch]$Apply
)

$ErrorActionPreference="Stop"
if([string]::IsNullOrWhiteSpace($SourceApiKey)){$SourceApiKey=[Environment]::GetEnvironmentVariable("SOURCE_ATTIO_API_KEY","User")}
if([string]::IsNullOrWhiteSpace($DevApiKey)){$DevApiKey=[Environment]::GetEnvironmentVariable("DEV_ATTIO_API_KEY","User")}
if([string]::IsNullOrWhiteSpace($SourceApiKey)){throw "Missing SOURCE_ATTIO_API_KEY."}
if([string]::IsNullOrWhiteSpace($DevApiKey)){throw "Missing DEV_ATTIO_API_KEY."}
if($Apply){
  $bounded=$Limit-ge1-and$Limit-le10-and$Confirmation-eq"APPLY_DEALS_TO_DEV"
  $full=$Limit-eq0-and$Confirmation-eq"APPLY_ALL_DEALS_TO_DEV"
  if(-not$bounded-and-not$full){throw "Use a 1-10 limit with APPLY_DEALS_TO_DEV, or Limit 0 with APPLY_ALL_DEALS_TO_DEV."}
}
$sh=@{Authorization="Bearer $($SourceApiKey.Trim())";Accept="application/json";"Content-Type"="application/json"}
$dh=@{Authorization="Bearer $($DevApiKey.Trim())";Accept="application/json";"Content-Type"="application/json"}
$decisions=Get-Content (Join-Path $PSScriptRoot "..\config\migration-decisions.json") -Raw|ConvertFrom-Json
$expectedWorkspaceId=[string]$decisions.dev_workspace_id
$outputPath=Join-Path $PSScriptRoot "..\..\outputs\attio_migration\deals-plan.json"
function Request{
  param([ValidateSet("Get","Post","Put")][string]$Method,[hashtable]$Headers,[string]$Path,[object]$Body)
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
function CheckboxValue($vs,$slug){
  $x=ActiveValue $vs $slug
  if($null-eq$x-or$null-eq$x.value){return $null}
  return [bool]$x.value
}
function MoneyValue($vs,$slug){
  $x=@($vs.$slug)|Where-Object{$null-eq$_.active_until}|Select-Object -First 1
  if($null-eq$x-or$null-eq$x.currency_value){return $null}
  if([string]$x.currency_code-ne"AED"){throw "Unexpected SOURCE Deal currency '$($x.currency_code)'; DEV Deal value is configured for AED."}
  return @{currency_value=[decimal]$x.currency_value}
}
$devObject=Request Get $dh "/objects/deals" $null
$workspaceId=[string]$devObject.data.id.workspace_id
if($workspaceId-ne$expectedWorkspaceId){throw "DEV workspace mismatch. Expected $expectedWorkspaceId but connected to $workspaceId."}
$source=@(All $sh "/objects/deals/records/query")
$dev=@(All $dh "/objects/deals/records/query")
$devOrganizations=@(All $dh "/objects/organizations/records/query")
$organizationByLegacy=@{}
foreach($r in $devOrganizations){
  $legacy=Value $r.values "legacy_attio_id"
  if(-not$legacy){continue}
  if($organizationByLegacy.ContainsKey([string]$legacy)){throw "Duplicate DEV Organization legacy_attio_id '$legacy'."}
  $organizationByLegacy[[string]$legacy]=Id $r
}
$sellerRoleEntries=@(All $dh "/lists/seller_role/entries/query")
$sellerRoleOrgIds=@{}
foreach($e in $sellerRoleEntries){
  $sellerRoleParentId=if($e.parent_record_id.record_id){[string]$e.parent_record_id.record_id}else{[string]$e.parent_record_id}
  if($sellerRoleParentId){$sellerRoleOrgIds[$sellerRoleParentId]=$true}
}
$byLegacy=@{}
foreach($r in $dev){$legacy=Value $r.values "legacy_attio_id";if($legacy){if($byLegacy.ContainsKey([string]$legacy)){throw "Duplicate DEV Deal legacy_attio_id."};$byLegacy[[string]$legacy]=$r}}

$statusMap=@{}
foreach($x in @((Request Get $dh "/objects/deals/attributes/stage/statuses" $null).data|Where-Object{-not$_.is_archived})){$statusMap[[string]$x.title]=[string]$x.id.status_id}
$teaserMap=@{}
foreach($x in @((Request Get $dh "/objects/deals/attributes/teaser_status/options" $null).data|Where-Object{-not$_.is_archived})){$teaserMap[[string]$x.title]=[string]$x.id.option_id}
$plans=[Collections.Generic.List[object]]::new()
foreach($s in $source){
  $sid=Id $s
  $existing=if($byLegacy.ContainsKey($sid)){$byLegacy[$sid]}else{$null}
  $action=if($null-ne$existing){"update"}else{"create"}
  $name=Value $s.values "name";if([string]::IsNullOrWhiteSpace([string]$name)){$name="Unknown Source Deal $sid"}
  $values=@{legacy_attio_id=$sid;name=[string]$name}
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
  $sourceSellerId=ReferenceId $s.values "associated_company"
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
    values=$values
  })
}
$unresolvedSellers=@($plans|Where-Object seller_resolution -ne "resolved")
if($unresolvedSellers.Count-gt0){
  throw "Cannot migrate Deals: $($unresolvedSellers.Count) seller relationship(s) did not resolve uniquely to DEV Organizations."
}
$populatedDevBuyers=@($dev|Where-Object{(Value $_.values "legacy_attio_id")-and@($_.values.buyer_id|Where-Object{$null-eq$_.active_until}).Count-gt0})
if($populatedDevBuyers.Count-gt0){
  throw "Confirmed migration rule requires blank buyer_id on SOURCE-migrated Deals, but $($populatedDevBuyers.Count) such DEV Deal(s) are populated. Review before applying."
}
$eligiblePlans=if($ExistingOnly){@($plans|Where-Object action -eq "update")}else{@($plans)}
$selected=if($Limit-eq0){@($eligiblePlans)}else{@($eligiblePlans|Select-Object -First $Limit)}
$selectedCreates=@($selected|Where-Object action -eq "create")
if($Apply-and$selectedCreates.Count-gt0-and[string]::IsNullOrWhiteSpace($DevOwnerWorkspaceMemberId)){
  throw "Attio requires Deal owner. Supply an approved DevOwnerWorkspaceMemberId to create $($selectedCreates.Count) missing Deal(s), or use -ExistingOnly."
}
$missingSellerRoleOrgIds=@{}
foreach($plan in $selected){
  if($plan.seller_org_id-and-not$sellerRoleOrgIds.ContainsKey($plan.seller_org_id)){
    $missingSellerRoleOrgIds[$plan.seller_org_id]=$true
  }
}
$missingSellerRoleOrgs=@($missingSellerRoleOrgIds.Keys)
$created=0;$updated=0;$errors=0;$sellerRoleCreated=0
if($Apply){
  foreach($orgId in $missingSellerRoleOrgs){
    Request Post $dh "/lists/seller_role/entries" @{data=@{parent_record_id=$orgId;parent_object="organizations";entry_values=@{}}}|Out-Null
    $sellerRoleCreated++
  }
  foreach($plan in $selected){
    $payload=@{};foreach($k in $plan.values.Keys){$payload[$k]=$plan.values[$k]}
    if($payload.ContainsKey("stage")){$title=[string]$payload.stage;if(-not$statusMap.ContainsKey($title)){throw "Missing DEV Deal stage '$title'."};$payload.stage=$statusMap[$title]}
    if($payload.ContainsKey("teaser_status")){$title=[string]$payload.teaser_status;if(-not$teaserMap.ContainsKey($title)){throw "Missing DEV teaser_status option '$title'."};$payload.teaser_status=$teaserMap[$title]}
    if($plan.action-eq"create"){$payload.owner=@{referenced_actor_type="workspace-member";referenced_actor_id=$DevOwnerWorkspaceMemberId}}
    try{
      if($plan.action-eq"update"){Request Put $dh "/objects/deals/records/$($plan.dev_record_id)" @{data=@{values=$payload}}|Out-Null;$updated++}
      else{$new=Request Post $dh "/objects/deals/records" @{data=@{values=$payload}};$plan.dev_record_id=Id $new.data;$created++}
    }catch{$errors++;throw}
  }
}
$summary=[ordered]@{mode=if($Apply){"apply"}else{"dry-run"};existing_only=[bool]$ExistingOnly;source_deals=$source.Count;existing_dev_deals=$dev.Count;resolved_existing=@($plans|Where-Object action -eq "update").Count;resolved_sellers=@($plans|Where-Object seller_resolution -eq "resolved").Count;unresolved_sellers=$unresolvedSellers.Count;populated_dev_buyers=$populatedDevBuyers.Count;would_create=@($plans|Where-Object action -eq "create").Count;owner_blocked_creates=if([string]::IsNullOrWhiteSpace($DevOwnerWorkspaceMemberId)){@($plans|Where-Object action -eq "create").Count}else{0};selected=$selected.Count;created=$created;updated=$updated;errors=$errors;missing_seller_role_orgs=$missingSellerRoleOrgs.Count;seller_role_created=$sellerRoleCreated}
[IO.Directory]::CreateDirectory((Split-Path $outputPath -Parent))|Out-Null
[IO.File]::WriteAllText($outputPath,([ordered]@{summary=$summary;plans=@($plans)}|ConvertTo-Json -Depth 30),[Text.UTF8Encoding]::new($false))
$summary|Format-List
Write-Host "Deal plan written to $outputPath"
if(-not$Apply){Write-Host "No Attio records were written."}

}
switch($Task){
 "record"{$a=@{Object=$Object;SourceApiKey=$SourceApiKey;DevApiKey=$DevApiKey;Limit=$Limit;StartOffset=$StartOffset;PageSize=$PageSize};if($Apply){$a.Apply=$true};Invoke-ObjectRecord @a}
 "parallel"{$a=@{Object=$Object;SourceApiKey=$SourceApiKey;DevApiKey=$DevApiKey;Workers=$Workers;PageSize=$PageSize};if($Apply){$a.Apply=$true};Invoke-ObjectParallel @a}
 "deals"{$a=@{SourceApiKey=$SourceApiKey;DevApiKey=$DevApiKey;Limit=$Limit;Confirmation=$Confirmation};if($DevOwnerWorkspaceMemberId){$a.DevOwnerWorkspaceMemberId=$DevOwnerWorkspaceMemberId};if($ExistingOnly){$a.ExistingOnly=$true};if($Apply){$a.Apply=$true};Invoke-Deals @a}
}
