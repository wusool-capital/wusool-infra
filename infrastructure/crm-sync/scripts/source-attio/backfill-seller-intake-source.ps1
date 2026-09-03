param(
  [string]$DevApiKey = $env:SOURCE_ATTIO_API_KEY,
  [switch]$Apply,
  [switch]$ClearIncorrect
)

# One-off backfill, not part of the recurring sync: intake_source has no
# SOURCE mapping and is confirmed write-once-except-correction (see
# FIELD_DECISIONS.md). Existing Seller Role entries with a blank
# intake_source are set to "Direct" per the approved manager decision --
# but only for entries whose parent Organization has a legacy_attio_id,
# i.e. actually came from the SOURCE migration. Seller Role entries on a
# DEV-native Organization (no legacy_attio_id, e.g. created directly via
# n8n) are left untouched and reported separately: their true
# intake_source is unknown and should not be assumed to be "Direct".
# Re-running is safe: only entries still blank are touched.

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($DevApiKey)) {
  $DevApiKey = [Environment]::GetEnvironmentVariable("SOURCE_ATTIO_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($DevApiKey)) { throw "Missing SOURCE_ATTIO_API_KEY." }

$headers = @{
  Authorization  = "Bearer $($DevApiKey.Trim())"
  Accept         = "application/json"
  "Content-Type" = "application/json"
}

function Request {
  param([ValidateSet("Get", "Post", "Patch")][string]$Method, [string]$Path, [object]$Body)
  $p = @{ Method = $Method; Uri = "https://api.attio.com/v2$Path"; Headers = $headers }
  if ($null -ne $Body) { $p.Body = [Text.Encoding]::UTF8.GetBytes(($Body | ConvertTo-Json -Depth 20)) }
  Invoke-RestMethod @p
}

function Get-ParentRecordId {
  param([object]$Entry)
  if ($Entry.parent_record_id.record_id) { return [string]$Entry.parent_record_id.record_id }
  if ($Entry.parent_record_id) { return [string]$Entry.parent_record_id }
  return $null
}

function Get-ActiveValue {
  param([object]$Values, [string]$Slug)
  $items = @($Values.$Slug | Where-Object { -not $_.active_until })
  if ($items.Count -eq 0) { return $null }
  return $items[0].value
}

$options = @((Request Get "/lists/seller_role/attributes/intake_source/options" $null).data)
$directOption = $options | Where-Object { -not $_.is_archived -and $_.title -eq "Direct" } | Select-Object -First 1
if (-not $directOption) {
  throw "DEV seller_role/intake_source has no 'Direct' option yet. Run 'ensure-schema.ps1 -Entities seller_role -Apply' first."
}
$directOptionId = [string]$directOption.id.option_id

Write-Host "Fetching DEV Organizations to identify SOURCE-derived orgs..."
$orgs = [Collections.Generic.List[object]]::new()
$offset = 0
while ($true) {
  $page = @((Request Post "/objects/organizations/records/query" @{ limit = 500; offset = $offset }).data)
  $orgs.AddRange($page)
  if ($page.Count -lt 500) { break }
  $offset += 500
}
$sourceDerivedOrgIds = @{}
foreach ($org in $orgs) {
  $legacyId = Get-ActiveValue -Values $org.values -Slug "legacy_attio_id"
  if ($legacyId) {
    $orgId = if ($org.id.record_id) { [string]$org.id.record_id } else { [string]$org.id }
    $sourceDerivedOrgIds[$orgId] = $true
  }
}
Write-Host "DEV Organizations: $($orgs.Count). SOURCE-derived (has legacy_attio_id): $($sourceDerivedOrgIds.Count)."

$entries = [Collections.Generic.List[object]]::new()
$offset = 0
while ($true) {
  $page = @((Request Post "/lists/seller_role/entries/query" @{ limit = 500; offset = $offset }).data)
  $entries.AddRange($page)
  if ($page.Count -lt 500) { break }
  $offset += 500
}

$blank = @($entries | Where-Object {
    @($_.entry_values.intake_source | Where-Object { -not $_.active_until }).Count -eq 0
  })

$sourceDerived = @($blank | Where-Object { $sourceDerivedOrgIds.ContainsKey((Get-ParentRecordId $_)) })
$devNative = @($blank | Where-Object { -not $sourceDerivedOrgIds.ContainsKey((Get-ParentRecordId $_)) })

Write-Host "Seller Role entries: $($entries.Count). Blank intake_source: $($blank.Count)."
Write-Host "  SOURCE-derived (parent org has legacy_attio_id) -> will backfill to Direct: $($sourceDerived.Count)"
Write-Host "  DEV-native (parent org has no legacy_attio_id) -> left alone, needs review: $($devNative.Count)"

foreach ($entry in $devNative) {
  $entryId = if ($entry.id.entry_id) { [string]$entry.id.entry_id } else { [string]$entry.entry_id }
  $orgId = Get-ParentRecordId $entry
  Write-Host "  SKIPPED (not SOURCE-derived): entry $entryId, parent org $orgId"
}

# Audit: entries that already carry a "Direct" value (set by something
# other than this script, e.g. a manual bulk edit) but whose parent org is
# DEV-native. These were not set by our controlled backfill and violate the
# approved rule that "Direct" is only the fallback for genuinely-unrecoverable
# SOURCE history -- report them regardless of -Apply, and only clear them if
# -ClearIncorrect is explicitly passed.
$alreadyDirect = @($entries | Where-Object {
    $active = @($_.entry_values.intake_source | Where-Object { -not $_.active_until })
    $active.Count -gt 0 -and [string]$active[0].option.title -eq "Direct"
  })
$incorrectlyDirect = @($alreadyDirect | Where-Object { -not $sourceDerivedOrgIds.ContainsKey((Get-ParentRecordId $_)) })
Write-Host ""
Write-Host "Audit: entries already set to 'Direct': $($alreadyDirect.Count)."
Write-Host "  Of those, on a DEV-native org (should NOT be 'Direct'): $($incorrectlyDirect.Count)"
foreach ($entry in $incorrectlyDirect) {
  $entryId = if ($entry.id.entry_id) { [string]$entry.id.entry_id } else { [string]$entry.entry_id }
  $orgId = Get-ParentRecordId $entry
  Write-Host "  INCORRECT: entry $entryId, parent org $orgId is DEV-native but shows 'Direct'"
}
if ($incorrectlyDirect.Count -gt 0) {
  if ($ClearIncorrect) {
    foreach ($entry in $incorrectlyDirect) {
      $entryId = if ($entry.id.entry_id) { [string]$entry.id.entry_id } else { [string]$entry.entry_id }
      if ($Apply) {
        Request Patch "/lists/seller_role/entries/$entryId" @{ data = @{ entry_values = @{ intake_source = @() } } } | Out-Null
        Write-Host "  CLEARED: entry $entryId"
      } else {
        Write-Host "  DRY RUN: would clear intake_source on entry $entryId"
      }
    }
  } else {
    Write-Host "  Pass -ClearIncorrect (with -Apply) to blank these back out."
  }
}

if (-not $Apply) {
  foreach ($entry in $sourceDerived) {
    $entryId = if ($entry.id.entry_id) { [string]$entry.id.entry_id } else { [string]$entry.entry_id }
    Write-Host "DRY RUN: would set intake_source -> Direct on entry $entryId"
  }
  Write-Host "Dry run complete. Add -Apply to write these $($sourceDerived.Count) updates."
  exit 0
}

$updated = 0
foreach ($entry in $sourceDerived) {
  $entryId = if ($entry.id.entry_id) { [string]$entry.id.entry_id } else { [string]$entry.entry_id }
  Request Patch "/lists/seller_role/entries/$entryId" @{ data = @{ entry_values = @{ intake_source = $directOptionId } } } | Out-Null
  $updated++
}
Write-Host "Backfill complete. Updated $updated SOURCE-derived entries to intake_source = Direct."
if ($devNative.Count -gt 0) {
  Write-Host "$($devNative.Count) DEV-native entries were left blank -- review their intake_source manually."
}
