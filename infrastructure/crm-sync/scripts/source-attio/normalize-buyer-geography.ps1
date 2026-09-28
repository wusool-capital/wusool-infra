param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [ValidateRange(0, 1000000)]
  [int]$Limit = 0,
  [switch]$IsTest,
  [string]$Confirmation,
  [switch]$Apply
)

# Splits `buyer_role.target_geography` into `target_region` and
# `target_country`.
#
# That one select held three different kinds of thing at once: countries (UAE,
# KSA, Kuwait, Bahrain, Qatar, Oman, Egypt), a region (GCC-wide) and a
# no-restriction marker (Global). Nothing downstream could tell them apart, so
# discovery had to guess per value -- and guessed wrong once: geocoding "GCC"
# returned Glendale Community College, California, with status OK, quietly
# restricting a Gulf search to Glendale.
#
# The new vocabularies are the Slack pickers' own: `target_region` is
# Organization.region's 14 titles plus Africa, Asia and Emerging Markets, which
# organization.geographic_focus carries; `target_country` mirrors
# Organization.hq_country (93 titles). Both use one canonical name per place,
# which is where `KSA` -> `Saudi Arabia` and `UAE` -> `United Arab Emirates`
# come from. A place should not have two names.
#
# This script only reads `target_geography`; it never writes or clears it. The
# attribute is archived by hand afterwards, once the new fields are verified
# and the server that reads them is deployed -- archiving it first would
# destroy the only copy of the data this script converts.
#
# A buyer role with no target_geography of its own inherits its parent
# organization's geographic_focus instead, mapped the same way. A value on the
# role always wins over one inherited from the company.
#
# Run this BEFORE split-buyer-roles-by-vertical.ps1. After the split there are
# ~989 entries to convert instead of 283, and the split would copy the old
# field onto every child.
#
# Re-runnable: an entry whose region and country already match what the mapping
# says is skipped, so this can ride along with every sync.

# ---------------------------------------------------------------------------
# WHAT MOVES, FROM WHERE TO WHERE
#
# Everything below happens inside Attio, on the buyer_role list. Postgres is a
# mirror and is never written here -- the nightly sync brings the result down.
#
#   READS (in priority order, per buyer_role entry)
#     1. buyer_role.target_geography       the entry's own value. Wins.
#     2. organizations.geographic_focus    the PARENT COMPANY's value, used
#                                          only when 1 is empty.
#
#   WRITES (same buyer_role entry, both fields, every time)
#     buyer_role.target_region             every region-type value
#     buyer_role.target_country            every country-type value
#
#   NEVER TOUCHED
#     buyer_role.target_geography          read-only here; archived by hand
#                                          afterwards, once verified
#     organizations.geographic_focus       read-only here; stays as it is
#     Postgres                             mirror only
#
#   VALUE MAP  (a title missing from it stops the run)
#     UAE, KSA                 -> country   United Arab Emirates, Saudi Arabia
#     Kuwait/Bahrain/Qatar/Oman/Egypt/Jordan/Pakistan/Morocco/Nigeria/
#       Kenya/South Africa/Kazakhstan/Saudi Arabia
#                              -> country   same name
#     USA                      -> country   United States
#     GCC-wide, GCC            -> region    GCC
#     SEA, LATAM               -> region    Southeast Asia, Latin America
#     MENA/Africa/Asia/Europe/Emerging Markets/Global
#                              -> region    same name
#
# THE OTHER WRITERS, all repointed in the same change, so nothing refills the
# old field behind this script:
#     SOURCE buyer_brain.target_geography  -> _internal/lists.ps1 now maps its
#                                             seven titles to region/country
#     the public buyer form                -> lead_magnets splits its answer
#     Slack /edit-buyer, /enrich-buyer     -> now offer region and country
#     the vertical split                   -> copies region/country to children
# ---------------------------------------------------------------------------

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($SourceApiKey)) {
  $SourceApiKey = [Environment]::GetEnvironmentVariable("SOURCE_ATTIO_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($SourceApiKey)) { throw "Missing SOURCE_ATTIO_API_KEY." }

$boundedToken = "APPLY_GEO_NORMALIZE_TO_SOURCE"
$fullToken = "APPLY_ALL_GEO_NORMALIZE_TO_SOURCE"
if ($Apply) {
  $isBoundedApply = $Limit -ge 1 -and $Limit -le 10 -and $Confirmation -eq $boundedToken
  $isFullApply = $Limit -eq 0 -and $Confirmation -eq $fullToken
  if (-not $isBoundedApply -and -not $isFullApply) {
    throw "Use a 1-10 -Limit with $boundedToken, or -Limit 0 with $fullToken."
  }
}

# Every title either source field can hold, and where it lands. A title missing
# from here stops the run rather than being dropped silently.
#
# Regions keep their own name -- Africa stays Africa rather than becoming
# "North Africa + Sub-Saharan Africa", which would claim a precision the record
# never had. Abbreviations are expanded, because that is the same rule that
# turns KSA into Saudi Arabia: one name per place.
$regionOf = @{
  "GCC-wide"         = "GCC"
  "GCC"              = "GCC"
  "MENA"             = "MENA"
  "MENATP"           = "MENATP"
  "Africa"           = "Africa"
  "Asia"             = "Asia"
  "Europe"           = "Europe"
  "SEA"              = "Southeast Asia"
  "LATAM"            = "Latin America"
  "Emerging Markets" = "Emerging Markets"
  "Global"           = "Global"
}
$countryOf = @{
  "UAE"          = "United Arab Emirates"
  "KSA"          = "Saudi Arabia"
  "Saudi Arabia" = "Saudi Arabia"
  "USA"          = "United States"
  "Kuwait"       = "Kuwait"
  "Bahrain"      = "Bahrain"
  "Qatar"        = "Qatar"
  "Oman"         = "Oman"
  "Egypt"        = "Egypt"
  "Jordan"       = "Jordan"
  "Pakistan"     = "Pakistan"
  "India"        = "India"
  "Morocco"      = "Morocco"
  "Nigeria"      = "Nigeria"
  "Kenya"        = "Kenya"
  "South Africa" = "South Africa"
  "Kazakhstan"   = "Kazakhstan"
}

$headers = @{
  Authorization = "Bearer $($SourceApiKey.Trim())"
  Accept = "application/json"
  "Content-Type" = "application/json"
}

$runId = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
$outputRoot = Join-Path $PSScriptRoot "..\..\..\..\outputs\attio_migration"
$null = New-Item -ItemType Directory -Force -Path $outputRoot

function Write-Json {
  param([string]$Path, [object]$Value)
  [IO.File]::WriteAllText(
    $Path, ($Value | ConvertTo-Json -Depth 40), [Text.UTF8Encoding]::new($false)
  )
}

function Invoke-AttioRequest {
  param(
    [ValidateSet("Get", "Post", "Patch")][string]$Method,
    [string]$Path,
    [object]$Body
  )
  $parameters = @{ Method = $Method; Uri = "https://api.attio.com/v2$Path"; Headers = $headers }
  if ($null -ne $Body) {
    $parameters.Body = [Text.Encoding]::UTF8.GetBytes(($Body | ConvertTo-Json -Depth 30))
  }
  for ($attempt = 1; ; $attempt++) {
    try { return Invoke-RestMethod @parameters }
    catch {
      $status = [int]$_.Exception.Response.StatusCode
      if ($attempt -ge 8 -or ($status -ne 429 -and $status -lt 500)) { throw }
      Start-Sleep -Seconds ([Math]::Min(5 * $attempt, 60))
    }
  }
}

function Get-PagedData {
  param([string]$Path)
  $all = @()
  for ($offset = 0; ; $offset += 500) {
    $response = Invoke-AttioRequest -Method Post -Path $Path -Body @{ limit = 500; offset = $offset }
    $page = @($response.data)
    $all += $page
    if ($page.Count -lt 500) { return $all }
  }
}

function Get-Titles {
  param([object]$Values, [string]$Slug)
  return @(
    $Values.$Slug |
      Where-Object { $null -eq $_.active_until } |
      ForEach-Object { if ($_.option.title) { [string]$_.option.title } else { [string]$_.value } } |
      Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
  )
}

# Attio's own `is_test` filter treats an unset checkbox as false, so scope is
# decided here on the raw value instead of in the query.
function Test-InScope {
  param([object]$Values)
  $item = @($Values.is_test) | Where-Object { $null -eq $_.active_until } | Select-Object -First 1
  $entryIsTest = if ($null -eq $item) { $false } else { [bool]$item.value }
  return $entryIsTest -eq [bool]$IsTest
}

$decisions = Get-Content (Join-Path $PSScriptRoot "config\migration-decisions.json") -Raw |
  ConvertFrom-Json
$expectedWorkspaceId = [string]$decisions.workspace_id
$organizationsObject = Invoke-AttioRequest -Method Get -Path "/objects/organizations"
$connectedWorkspaceId = [string]$organizationsObject.data.id.workspace_id
if ($connectedWorkspaceId -ne $expectedWorkspaceId) {
  throw "Workspace mismatch. Expected $expectedWorkspaceId but connected to $connectedWorkspaceId."
}

$optionMaps = @{}
foreach ($field in @("target_region", "target_country")) {
  $response = Invoke-AttioRequest -Method Get -Path "/lists/buyer_role/attributes/$field/options"
  $map = @{}
  foreach ($option in @($response.data | Where-Object { -not $_.is_archived })) {
    $map[[string]$option.title] = [string]$option.id.option_id
  }
  if ($map.Count -eq 0) {
    throw "buyer_role/$field has no options. Run ensure-schema.ps1 -Apply first."
  }
  $optionMaps[$field] = $map
}

Write-Host "Reading buyer_role entries and organizations..."
$allEntries = Get-PagedData -Path "/lists/buyer_role/entries/query"
$organizations = Get-PagedData -Path "/objects/organizations/records/query"
$orgById = @{}
foreach ($record in $organizations) { $orgById[[string]$record.id.record_id] = $record }

function Get-ParentRecordId {
  param([object]$Entry)
  if ($Entry.parent_record_id.record_id) { return [string]$Entry.parent_record_id.record_id }
  if ($Entry.parent_record_id) { return [string]$Entry.parent_record_id }
  return $null
}

Write-Json -Path (Join-Path $outputRoot "buyer-role-geo-backup-$runId.json") -Value @{
  captured_at_utc = [DateTime]::UtcNow.ToString("o")
  list = "buyer_role"
  entry_count = $allEntries.Count
  entries = $allEntries
}

$plans = [Collections.Generic.List[object]]::new()
$skipped = [ordered]@{ no_geography = 0; already_normalized = 0 }
$valueCounts = @{}
$fromFallback = 0

foreach ($entry in @($allEntries | Where-Object { Test-InScope -Values $_.entry_values })) {
  $values = $entry.entry_values
  $titles = @(Get-Titles -Values $values -Slug "target_geography")
  # A value set on the buyer role always wins. Only when it has none do we
  # inherit the parent company's geographic_focus -- which is the one field
  # that actually holds this data today, buyer_role.geographic_focus having
  # never been written.
  $source = "target_geography"
  if ($titles.Count -eq 0) {
    $org = $orgById[(Get-ParentRecordId -Entry $entry)]
    if ($null -ne $org) {
      $titles = @(Get-Titles -Values $org.values -Slug "geographic_focus")
      if ($titles.Count -gt 0) { $source = "organization.geographic_focus"; $fromFallback++ }
    }
  }
  if ($titles.Count -eq 0) { $skipped.no_geography++; continue }

  $regions = [Collections.Generic.List[string]]::new()
  $countries = [Collections.Generic.List[string]]::new()
  foreach ($title in $titles) {
    if (-not $valueCounts.ContainsKey($title)) { $valueCounts[$title] = 0 }
    $valueCounts[$title]++
    if ($regionOf.ContainsKey($title)) {
      if (-not $regions.Contains($regionOf[$title])) { $regions.Add($regionOf[$title]) }
    } elseif ($countryOf.ContainsKey($title)) {
      if (-not $countries.Contains($countryOf[$title])) { $countries.Add($countryOf[$title]) }
    } else {
      throw "target_geography value '$title' has no mapping. Add it to this script before running."
    }
  }

  $currentRegions = @(Get-Titles -Values $values -Slug "target_region")
  $currentCountries = @(Get-Titles -Values $values -Slug "target_country")
  $regionsMatch = $currentRegions.Count -eq $regions.Count -and
    @(Compare-Object $currentRegions @($regions)).Count -eq 0
  $countriesMatch = $currentCountries.Count -eq $countries.Count -and
    @(Compare-Object $currentCountries @($countries)).Count -eq 0
  if ($regionsMatch -and $countriesMatch) { $skipped.already_normalized++; continue }

  $payload = @{}
  foreach ($pair in @(
    @{ field = "target_region"; titles = @($regions) },
    @{ field = "target_country"; titles = @($countries) }
  )) {
    $ids = [Collections.Generic.List[string]]::new()
    foreach ($title in $pair.titles) {
      if (-not $optionMaps[$pair.field].ContainsKey($title)) {
        throw "buyer_role/$($pair.field) has no option '$title'. Run ensure-schema.ps1 -Apply first."
      }
      $ids.Add($optionMaps[$pair.field][$title])
    }
    # Written even when empty: a buyer with only countries must end up with an
    # empty region, not whatever a previous run happened to leave there.
    $payload[$pair.field] = @($ids)
  }

  $plans.Add([ordered]@{
    entry_id = [string]$entry.id.entry_id
    org_attio_id = if ($entry.parent_record_id.record_id) {
      [string]$entry.parent_record_id.record_id
    } else {
      [string]$entry.parent_record_id
    }
    source = $source
    from = @($titles)
    target_region = @($regions)
    target_country = @($countries)
    values = $payload
  })
}

if ($Limit -gt 0 -and $plans.Count -gt $Limit) {
  $plans = [Collections.Generic.List[object]](@($plans | Select-Object -First $Limit))
}

$applyStats = [ordered]@{ patched = 0; errors = 0 }
if ($Apply) {
  foreach ($plan in $plans) {
    try {
      Invoke-AttioRequest -Method Patch -Path "/lists/buyer_role/entries/$($plan.entry_id)" `
        -Body @{ data = @{ entry_values = $plan.values } } | Out-Null
      $applyStats.patched++
    } catch {
      $applyStats.errors++
      throw
    }
  }
} else {
  foreach ($plan in $plans) {
    Write-Host ("DRY RUN: {0} -> region [{1}] country [{2}]" -f `
      ($plan.from -join ", "), ($plan.target_region -join ", "), ($plan.target_country -join ", "))
  }
}

$summary = [ordered]@{
  generated_at_utc = [DateTime]::UtcNow.ToString("o")
  run_id = $runId
  mode = if ($Apply) { if ($Limit -eq 0) { "apply" } else { "bounded-apply" } } else { "dry-run" }
  scope = if ($IsTest) { "test" } else { "production" }
  entries_in_list = $allEntries.Count
  planned_patches = $plans.Count
  from_target_geography = @($plans | Where-Object { $_.source -eq "target_geography" }).Count
  from_organization_fallback = @($plans | Where-Object { $_.source -ne "target_geography" }).Count
  region_assignments = @($plans | Where-Object { $_.target_region.Count -gt 0 }).Count
  country_assignments = @($plans | Where-Object { $_.target_country.Count -gt 0 }).Count
  source_values = $valueCounts
  skipped = $skipped
  apply = $applyStats
}

Write-Json -Path (Join-Path $outputRoot "buyer-role-geo-plan.json") -Value @{
  summary = $summary
  sample = @($plans | Select-Object -First 10)
  plans = $plans
}

$summary | Format-List
Write-Host "Backup: $outputRoot\buyer-role-geo-backup-$runId.json"
Write-Host "Plan:   $outputRoot\buyer-role-geo-plan.json"
