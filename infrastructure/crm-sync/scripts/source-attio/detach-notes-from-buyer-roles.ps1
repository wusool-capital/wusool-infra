param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [ValidateRange(0, 1000000)]
  [int]$Limit = 0,
  [switch]$IsTest,
  [string]$Confirmation,
  [switch]$Apply
)

# Moves meeting notes off individual buyer_role entries and up to the
# organization.
#
# Before the vertical re-grain a buyer had one buyer_role entry, so pointing a
# note at it and pointing it at the company said the same thing. After the
# split an organization has one entry per vertical -- 990 entries across 254
# organizations -- and note.buyer_role_id still points at whichever entry was
# patched in place. That entry is the organization's FIRST sector and nothing
# more, so the note now reads as though the conversation was about that one
# vertical, which nobody ever asserted.
#
# A note carries no signal saying which vertical it concerned. Unlike
# match_results, which can be re-filed using the seller's sector, there is
# nothing here to re-file by. So the link is dropped rather than guessed.
#
# Notes live at organization level, full stop. Every linked note is detached,
# including the 43 whose organization still has exactly one live vertical and
# whose link is therefore still technically correct -- one rule, one class of
# note. The per-organization vertical count is still recorded in the plan JSON
# so it stays visible which those 43 were.
#
# primary_role is deliberately NOT set. It is empty on all 178 of these notes,
# so once this runs the only record that they were buyer conversations is the
# organization they hang off. That was the call made on 2026-09-27: clear the
# buyer id, nothing else.
#
# Re-runnable: a note with no buyer_role_id is skipped.

# ---------------------------------------------------------------------------
# WHAT MOVES, FROM WHERE TO WHERE
#
# Everything below happens inside Attio, on the note object. Postgres is a
# mirror and is never written here -- the nightly sync brings the result down,
# nulling notes.buyer_role_id (a nullable FK that nothing queries).
#
#   READS
#     note.buyer_role_id           the buyer_role ENTRY id, as text
#     note.organization_id         record-reference to organizations, read only
#                                  to confirm the note has one before detaching
#     buyer_role entries           read-only, to resolve the entry to its
#                                  parent org and count that org's verticals
#
#   WRITES -- ONE attribute, on the note record only
#     note.buyer_role_id  -> cleared
#
#   NEVER TOUCHED
#     note.organization_id, primary_role, seller_role_id, person_id, content,
#       note_type, legacy_note_id, note_created_at, is_test
#     buyer_role entries           no entry is patched or deleted
#     Postgres                     mirror only
#
# THE ONE WAY THIS SILENTLY REVERTS
#   backfill-notes.ps1 writes buyer_role_id on every update. Run it again
#   without -CreateOnly and all 178 links come straight back. From here that
#   script is create-only; see config/migration-decisions.json.
# ---------------------------------------------------------------------------

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($SourceApiKey)) {
  $SourceApiKey = [Environment]::GetEnvironmentVariable("SOURCE_ATTIO_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($SourceApiKey)) { throw "Missing SOURCE_ATTIO_API_KEY." }

$boundedToken = "APPLY_NOTE_DETACH_TO_SOURCE"
$fullToken = "APPLY_ALL_NOTE_DETACH_TO_SOURCE"
if ($Apply) {
  $isBoundedApply = $Limit -ge 1 -and $Limit -le 10 -and $Confirmation -eq $boundedToken
  $isFullApply = $Limit -eq 0 -and $Confirmation -eq $fullToken
  if (-not $isBoundedApply -and -not $isFullApply) {
    throw "Use a 1-10 -Limit with $boundedToken, or -Limit 0 with $fullToken."
  }
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

function Get-ActiveValues {
  param([object]$Values, [string]$Slug)
  return @($Values.$Slug | Where-Object { $null -eq $_.active_until })
}

function Get-Title {
  param([object]$Values, [string]$Slug)
  $item = @(Get-ActiveValues -Values $Values -Slug $Slug) | Select-Object -First 1
  if ($null -eq $item) { return $null }
  if ($item.option.title) { return [string]$item.option.title }
  $text = [string]$item.value
  if ([string]::IsNullOrWhiteSpace($text)) { return $null }
  return $text
}

function Get-Reference {
  param([object]$Values, [string]$Slug)
  $item = @(Get-ActiveValues -Values $Values -Slug $Slug) | Select-Object -First 1
  if ($null -eq $item) { return $null }
  return [string]$item.target_record_id
}

function Get-Checkbox {
  param([object]$Values, [string]$Slug)
  $item = @(Get-ActiveValues -Values $Values -Slug $Slug) | Select-Object -First 1
  if ($null -eq $item) { return $false }
  return [bool]$item.value
}

# Attio's own `is_test` filter treats an unset checkbox as false, so scope is
# decided here on the raw value instead of in the query.
function Test-InScope {
  param([object]$Values)
  return (Get-Checkbox -Values $Values -Slug "is_test") -eq [bool]$IsTest
}

function Get-ParentRecordId {
  param([object]$Entry)
  if ($Entry.parent_record_id.record_id) { return [string]$Entry.parent_record_id.record_id }
  if ($Entry.parent_record_id) { return [string]$Entry.parent_record_id }
  return $null
}

$decisions = Get-Content (Join-Path $PSScriptRoot "config\migration-decisions.json") -Raw |
  ConvertFrom-Json
$expectedWorkspaceId = [string]$decisions.workspace_id
$organizationsObject = Invoke-AttioRequest -Method Get -Path "/objects/organizations"
$connectedWorkspaceId = [string]$organizationsObject.data.id.workspace_id
if ($connectedWorkspaceId -ne $expectedWorkspaceId) {
  throw "Workspace mismatch. Expected $expectedWorkspaceId but connected to $connectedWorkspaceId."
}

Write-Host "Reading buyer_role entries and notes..."
$allEntries = Get-PagedData -Path "/lists/buyer_role/entries/query"
$allNotes = Get-PagedData -Path "/objects/note/records/query"

# entry id -> parent org, and org -> how many verticals are live on it. Both
# scopes are indexed rather than just the in-scope one: a note is matched to
# its entry regardless of is_test, so a mis-stamped pair is reported as such
# instead of looking like a deleted entry.
$orgOfEntry = @{}
$liveVerticalsOfOrg = @{}
foreach ($entry in $allEntries) {
  $entryId = [string]$entry.id.entry_id
  $orgId = Get-ParentRecordId -Entry $entry
  $orgOfEntry[$entryId] = $orgId
  if (Get-Checkbox -Values $entry.entry_values -Slug "is_active") {
    if (-not $liveVerticalsOfOrg.ContainsKey($orgId)) { $liveVerticalsOfOrg[$orgId] = 0 }
    $liveVerticalsOfOrg[$orgId]++
  }
}

Write-Json -Path (Join-Path $outputRoot "note-detach-backup-$runId.json") -Value @{
  captured_at_utc = [DateTime]::UtcNow.ToString("o")
  object = "note"
  record_count = $allNotes.Count
  records = $allNotes
}

$plans = [Collections.Generic.List[object]]::new()
$skipped = [ordered]@{ already_detached = 0 }
$dangling = [Collections.Generic.List[string]]::new()
$stillUnambiguous = 0

foreach ($note in @($allNotes | Where-Object { Test-InScope -Values $_.values })) {
  $values = $note.values
  $roleEntryId = Get-Title -Values $values -Slug "buyer_role_id"
  if (-not $roleEntryId) { $skipped.already_detached++; continue }

  # An entry id that no longer resolves is reported, not cleared: it means the
  # entry was deleted, which is not something this migration did, and someone
  # should know before the last reference to it disappears.
  if (-not $orgOfEntry.ContainsKey($roleEntryId)) {
    $dangling.Add([string]$note.id.record_id)
    continue
  }

  $orgId = $orgOfEntry[$roleEntryId]
  $liveCount = 0
  if ($liveVerticalsOfOrg.ContainsKey($orgId)) { $liveCount = $liveVerticalsOfOrg[$orgId] }
  if ($liveCount -le 1) { $stillUnambiguous++ }

  # An empty array is how Attio clears a value.
  $payload = @{ buyer_role_id = @() }
  $actions = [Collections.Generic.List[string]]::new()
  $actions.Add("clear buyer_role_id")

  # The organization link is what the note falls back to, so it has to exist
  # before the role link goes -- detaching a note that has neither would leave
  # it attached to nothing. All 178 have one today, so this never fires; it
  # stops the run rather than repairing anything, because this script writes
  # one attribute and only one.
  if (-not (Get-Reference -Values $values -Slug "organization_id")) {
    throw "Note $($note.id.record_id) has no organization_id; detaching it would orphan it."
  }

  $plans.Add([ordered]@{
    record_id = [string]$note.id.record_id
    org_attio_id = $orgId
    buyer_role_entry_id = $roleEntryId
    live_verticals_on_org = $liveCount
    ambiguous = ($liveCount -gt 1)
    actions = @($actions)
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
      Invoke-AttioRequest -Method Patch -Path "/objects/note/records/$($plan.record_id)" `
        -Body @{ data = @{ values = $plan.values } } | Out-Null
      $applyStats.patched++
    } catch {
      $applyStats.errors++
      throw
    }
  }
} else {
  foreach ($plan in $plans) {
    Write-Host ("DRY RUN: note {0} (org has {1} live vertical(s)) -> {2}" -f `
      $plan.record_id, $plan.live_verticals_on_org, ($plan.actions -join "; "))
  }
}

if ($dangling.Count -gt 0) {
  Write-Warning "$($dangling.Count) note(s) point at a buyer_role entry that no longer exists; left untouched."
}

$summary = [ordered]@{
  generated_at_utc = [DateTime]::UtcNow.ToString("o")
  run_id = $runId
  mode = if ($Apply) { if ($Limit -eq 0) { "apply" } else { "bounded-apply" } } else { "dry-run" }
  scope = if ($IsTest) { "test" } else { "production" }
  notes_in_object = $allNotes.Count
  buyer_role_entries = $allEntries.Count
  planned_patches = $plans.Count
  detaching = $plans.Count
  # Reporting only: these were the links still pointing at the one vertical
  # their organization has, and are detached anyway under the one-rule policy.
  detached_though_unambiguous = $stillUnambiguous
  dangling_role_ids = $dangling.Count
  skipped = $skipped
  apply = $applyStats
}

Write-Json -Path (Join-Path $outputRoot "note-detach-plan.json") -Value @{
  summary = $summary
  dangling_record_ids = @($dangling)
  sample = @($plans | Select-Object -First 10)
  plans = $plans
}

$summary | Format-List
Write-Host "Backup: $outputRoot\note-detach-backup-$runId.json"
Write-Host "Plan:   $outputRoot\note-detach-plan.json"
