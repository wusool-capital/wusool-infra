param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [int]$Limit = 0,
  [ValidateRange(1, 16)]
  [int]$Workers = 8,
  [string]$Confirmation,
  [switch]$Apply
)

# One-off backfill, not part of the recurring sync-all-within-source.ps1
# entity loop (though it IS wired in as that pipeline's last step -- see
# sync-all-within-source.ps1): populates the new `note` custom object
# (plural noun "Unified Notes", slug `note` -- "notes" is reserved by Attio
# itself, presumably for its own native per-record Notes feature; created
# manually in the Attio UI, this script only manages its attributes and
# records, never its creation) from three SOURCE-Attio-only sources -- both
# note_type=Manual and note_type=Meeting, in one script and one -Apply:
#   - native Companies' own per-record Notes panel (GET /v2/notes)
#   - native People's own per-record Notes panel
#   - the already-migrated `buyer_role` list's own `notes` text field
#
# Manual vs Meeting: native notes don't carry an explicit type of their own,
# but meeting summaries pushed into Attio (e.g. via Granola's own Attio
# integration) reliably contain a "notes.granola.ai" transcript link in the
# body -- confirmed live against a real example (Ghobash Group). Get-NoteType
# below classifies on that; anything without it is Manual. Buyer Role's
# `notes` text field is always Manual (a mandate note, never a meeting
# summary). No Postgres involved anywhere -- meeting content that already
# made it into Attio's native notes doesn't need a second source, and a
# Postgres `meetings` pass was deliberately dropped to avoid double-creating
# the same meeting under two different legacy_note_id namespaces.
#
# `organization_id`/`person_id` link to the already-migrated `organizations`/
# `person` custom objects (matched via their `legacy_attio_id`), not the
# native Companies/People records directly -- those migrated objects are what
# the rest of the pipeline, and eventually DEV Attio / PostgreSQL, actually
# reference. A native Company/Person with no matching migrated record yet is
# skipped and counted, not linked to nothing.
#
# A migrated Person with no company of their own (confirmed live, 2026-08-29:
# some SOURCE contacts genuinely have no company on either of SOURCE's own
# company-reference fields, not a sync gap) still gets their notes migrated,
# just with organization_id left blank -- person_id alone is enough of an
# anchor. Native Company notes have no such fallback (a Company note is never
# person-linked), so a Company with no migrated Organization is still skipped
# outright.
#
# `buyer_role_id`/`seller_role_id` are plain text (the list entry_id), not
# record-reference: Attio's record-reference type targets Objects, not List
# entries, and buyer_role/seller_role are lists. Fine here -- Attio is a
# mirrored view for this table, not the source of truth (PostgreSQL will
# enforce the real FK later). Only set for Buyer Role's own notes (which know
# their entry directly) -- native Meeting notes have no reliable buy/sell
# signal to resolve these from, so they're left blank rather than guessed.
#
# `legacy_note_id` is not part of the original design doc's field list, but
# every other entity in this migration has an idempotency key
# (legacy_attio_id / legacy_entry_id) for exactly this reason: without one,
# re-running this backfill would create duplicate note records every time.
# Namespaced per source: `note:{attio note id}`, `buyer_role:{entry id}`.
#
# DEV Attio and PostgreSQL are out of scope here (explicitly deferred) -- no
# DEV key, no DATABASE_URL, nothing outside this SOURCE workspace is touched.

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($SourceApiKey)) {
  $SourceApiKey = [Environment]::GetEnvironmentVariable("SOURCE_ATTIO_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($SourceApiKey)) { throw "Missing SOURCE_ATTIO_API_KEY." }
if ($Apply -and $Confirmation -ne "APPLY_NOTES_BACKFILL_TO_SOURCE") {
  throw "Pass -Apply -Confirmation APPLY_NOTES_BACKFILL_TO_SOURCE to write."
}

$headers = @{
  Authorization  = "Bearer $($SourceApiKey.Trim())"
  Accept         = "application/json"
  "Content-Type" = "application/json"
}

function Request {
  param([ValidateSet("Get", "Post", "Put")][string]$Method, [string]$Path, [object]$Body)
  for ($attempt = 1; $attempt -le 8; $attempt++) {
    try {
      $p = @{ Method = $Method; Uri = "https://api.attio.com/v2$Path"; Headers = $headers }
      if ($null -ne $Body) { $p.Body = [Text.Encoding]::UTF8.GetBytes(($Body | ConvertTo-Json -Depth 20)) }
      return Invoke-RestMethod @p
    } catch {
      $status = 0
      if ($_.Exception.Response) { $status = [int]$_.Exception.Response.StatusCode }
      if ($attempt -eq 8 -or ($status -ne 429 -and $status -lt 500)) { throw }
      $delay = [Math]::Min(60, 5 * $attempt)
      Write-Warning "Attio $Method $Path returned HTTP $status. Retrying in $delay seconds."
      Start-Sleep -Seconds $delay
    }
  }
}

function Get-Value {
  param([object]$Values, [string]$Slug)
  $item = @($Values.$Slug) | Where-Object { -not $_.active_until } | Select-Object -First 1
  if ($null -eq $item) { return $null }
  if ($item.target_record_id) { return [string]$item.target_record_id }
  if ($null -ne $item.value) { return [string]$item.value }
  if ($item.option.title) { return [string]$item.option.title }
  return $null
}

function Get-AllRecords {
  param([string]$ObjectSlug)
  $items = [Collections.Generic.List[object]]::new()
  $offset = 0
  while ($true) {
    $page = @((Request Post "/objects/$ObjectSlug/records/query" @{ limit = 500; offset = $offset }).data)
    $items.AddRange($page)
    if ($page.Count -lt 500) { break }
    $offset += 500
  }
  return $items
}

$decisions = Get-Content (Join-Path $PSScriptRoot "config\migration-decisions.json") -Raw | ConvertFrom-Json
$expectedWorkspaceId = [string]$decisions.dev_workspace_id

$notesObj = Request Get "/objects/note" $null
if ([string]$notesObj.data.api_slug -ne "note") {
  throw "The custom 'note' object was not found. Create it manually first (plural noun 'Unified Notes', slug 'note')."
}
if ([string]$notesObj.data.id.workspace_id -ne $expectedWorkspaceId) {
  throw "Workspace mismatch. Expected $expectedWorkspaceId but connected to $($notesObj.data.id.workspace_id)."
}

# --- 1. Ensure the notes object's attributes exist -------------------------

function Get-Attributes {
  param([switch]$IncludeArchived)
  $suffix = if ($IncludeArchived) { "?show_archived=true" } else { "" }
  $resp = Request Get "/objects/note/attributes$suffix" $null
  $map = @{}
  foreach ($a in @($resp.data)) { $map[[string]$a.api_slug] = $a }
  return $map
}

$fields = @(
  [pscustomobject]@{ Title = "Organization"; Slug = "organization_id"; Type = "record-reference"; Unique = $false; Config = @{ record_reference = @{ allowed_objects = @("organizations") } } },
  [pscustomobject]@{ Title = "Person"; Slug = "person_id"; Type = "record-reference"; Unique = $false; Config = @{ record_reference = @{ allowed_objects = @("person") } } },
  [pscustomobject]@{ Title = "Buyer Role ID"; Slug = "buyer_role_id"; Type = "text"; Unique = $false; Config = @{} },
  [pscustomobject]@{ Title = "Seller Role ID"; Slug = "seller_role_id"; Type = "text"; Unique = $false; Config = @{} },
  [pscustomobject]@{ Title = "Note Type"; Slug = "note_type"; Type = "select"; Unique = $false; Config = @{}; FixedOptions = @("Manual", "Meeting") },
  [pscustomobject]@{ Title = "Content"; Slug = "content"; Type = "text"; Unique = $false; Config = @{} },
  # Slug is `note_created_at`, NOT `created_at`: every Attio custom object
  # auto-provisions its own protected, system-owned "Created At" timestamp
  # (confirmed live, 2026-08-28 -- writes to it fail with
  # "system_edit_unauthorized"), always set to whenever the API call
  # actually runs, never backdatable. This field holds the note's REAL
  # original timestamp instead.
  [pscustomobject]@{ Title = "Note Created At"; Slug = "note_created_at"; Type = "timestamp"; Unique = $false; Config = @{} },
  [pscustomobject]@{ Title = "Legacy Note ID"; Slug = "legacy_note_id"; Type = "text"; Unique = $true; Config = @{} }
)

$attrs = Get-Attributes
$schemaActions = [Collections.Generic.List[string]]::new()
foreach ($field in $fields) {
  if ($attrs.ContainsKey($field.Slug)) {
    $current = $attrs[$field.Slug]
    if ([string]$current.type -ne $field.Type) {
      throw "note/$($field.Slug) exists with type=$($current.type); expected type=$($field.Type)."
    }
    Write-Host "EXISTS: $($field.Slug)"
    continue
  }
  $schemaActions.Add("create_attribute:$($field.Slug)")
  if ($Apply) {
    Request Post "/objects/note/attributes" @{
      data = @{
        title          = $field.Title
        description    = "Wusool Notes target field."
        api_slug       = $field.Slug
        type           = $field.Type
        is_required    = $false
        is_unique      = [bool]$field.Unique
        is_multiselect = $false
        config         = $field.Config
      }
    } | Out-Null
    Write-Host "CREATED: $($field.Slug)"
  } else {
    Write-Host "DRY RUN: would create $($field.Slug) ($($field.Type))."
  }
}

if ($Apply) { $attrs = Get-Attributes }
foreach ($field in @($fields | Where-Object FixedOptions)) {
  if (-not $Apply -and -not $attrs.ContainsKey($field.Slug)) {
    foreach ($title in $field.FixedOptions) {
      Write-Host "DRY RUN: would create $($field.Slug) option '$title'."
      $schemaActions.Add("create_option:$($field.Slug):$title")
    }
    continue
  }
  $existing = @{}
  foreach ($o in @((Request Get "/objects/note/attributes/$($field.Slug)/options" $null).data | Where-Object { -not $_.is_archived })) {
    $existing[[string]$o.title.Trim().ToLowerInvariant()] = $true
  }
  foreach ($title in $field.FixedOptions) {
    $key = $title.Trim().ToLowerInvariant()
    if ($existing.ContainsKey($key)) { continue }
    $schemaActions.Add("create_option:$($field.Slug):$title")
    if ($Apply) {
      Request Post "/objects/note/attributes/$($field.Slug)/options" @{ data = @{ title = $title } } | Out-Null
      Write-Host "CREATED OPTION: $($field.Slug) -> $title"
    } else {
      Write-Host "DRY RUN: would create $($field.Slug) option '$title'."
    }
  }
}

if (-not $Apply -and $schemaActions.Count -gt 0) {
  Write-Host ""
  Write-Host "Schema dry run: $($schemaActions.Count) planned action(s). Re-run with -Apply to create them before the record backfill can proceed for real."
}

# --- 2. Load identity maps --------------------------------------------------

Write-Host ""
Write-Host "Loading migrated Organizations and People..."
$orgRecords = Get-AllRecords -ObjectSlug "organizations"
$personRecords = Get-AllRecords -ObjectSlug "person"

$orgByLegacyId = @{}
foreach ($r in $orgRecords) {
  $legacy = Get-Value -Values $r.values -Slug "legacy_attio_id"
  if ($legacy) { $orgByLegacyId[$legacy] = [string]$r.id.record_id }
}
$personByLegacyId = @{}
$personOrgId = @{}
foreach ($r in $personRecords) {
  $legacy = Get-Value -Values $r.values -Slug "legacy_attio_id"
  if ($legacy) { $personByLegacyId[$legacy] = [string]$r.id.record_id }
  $companyRef = Get-Value -Values $r.values -Slug "company"
  if ($companyRef) { $personOrgId[[string]$r.id.record_id] = $companyRef }
}
Write-Host "Organizations: $($orgRecords.Count) ($($orgByLegacyId.Count) with legacy_attio_id). Person: $($personRecords.Count) ($($personByLegacyId.Count) with legacy_attio_id)."

Write-Host "Loading existing Notes records for idempotency..."
$existingNotes = Get-AllRecords -ObjectSlug "note"
$notesByLegacyId = @{}
foreach ($r in $existingNotes) {
  $legacy = Get-Value -Values $r.values -Slug "legacy_note_id"
  if ($legacy) {
    $notesByLegacyId[$legacy] = [pscustomobject]@{
      RecordId = [string]$r.id.record_id
      Content  = Get-Value -Values $r.values -Slug "content"
      NoteType = Get-Value -Values $r.values -Slug "note_type"
    }
  }
}
Write-Host "Existing Notes records: $($existingNotes.Count) ($($notesByLegacyId.Count) with legacy_note_id)."

# --- 3. Collect notes to create/update --------------------------------------
#
# Not create-only: an existing note whose SOURCE content has since changed
# (e.g. a Granola meeting thread getting more detail added after the fact)
# gets updated in place, not left stale forever -- confirmed a real gap via
# validate-notes.ps1, 2026-08-28. Compared by content only (not note_type),
# since note_type is derived from content anyway.

$toCreate = [Collections.Generic.List[object]]::new()
$toUpdate = [Collections.Generic.List[object]]::new()

function Add-Note {
  param([string]$LegacyNoteId, [string]$OrganizationId, [string]$PersonId, [string]$BuyerRoleId, [string]$Content, [string]$CreatedAt, [string]$NoteType = "Manual")
  if ([string]::IsNullOrWhiteSpace($Content)) { return }
  if ([string]::IsNullOrWhiteSpace($OrganizationId) -and [string]::IsNullOrWhiteSpace($PersonId)) { return }
  $existing = $notesByLegacyId[$LegacyNoteId]
  if ($existing) {
    if ([string]$existing.Content -ne [string]$Content) {
      $toUpdate.Add([pscustomobject]@{
          RecordId       = $existing.RecordId
          LegacyNoteId   = $LegacyNoteId
          OrganizationId = $OrganizationId
          PersonId       = $PersonId
          BuyerRoleId    = $BuyerRoleId
          Content        = $Content
          CreatedAt      = $CreatedAt
          NoteType       = $NoteType
        })
    }
    return
  }
  $toCreate.Add([pscustomobject]@{
      LegacyNoteId   = $LegacyNoteId
      OrganizationId = $OrganizationId
      PersonId       = $PersonId
      BuyerRoleId    = $BuyerRoleId
      Content        = $Content
      CreatedAt      = $CreatedAt
      NoteType       = $NoteType
    })
}

function Get-RawNoteBody {
  param([object]$Note)
  if ($Note.content_plaintext) { return [string]$Note.content_plaintext }
  return [string]$Note.content_markdown
}

# Meeting summaries pushed into Attio (confirmed live: Granola's own Attio
# integration) reliably link back to "notes.granola.ai" or say "Chat with
# meeting transcript" in the body. Native notes have no explicit type field
# of their own, so this is the only signal available to tell a meeting
# summary apart from a genuinely hand-typed note. Classifies on the RAW body,
# before Format-NoteContent strips that same trailer out -- otherwise
# classification would never fire.
function Get-NoteType {
  param([object]$Note)
  $body = Get-RawNoteBody -Note $Note
  if ($body -match '(?i)granola\.ai|chat with meeting transcript') { return "Meeting" }
  return "Manual"
}

# Native Attio notes carry a title separate from their body (e.g. "Follow Up
# From LinkedIn Message - Sell-Side Opportunities...") -- content alone would
# silently drop it. Prepended as a markdown heading unless the body already
# starts with it (Attio sometimes duplicates the title as the body's first
# line already).
#
# For Meeting notes specifically, content should be the summary itself --
# the Granola<>Attio integration appends a "---" separator + transcript link
# footer and sometimes an "Added by: X" attribution line, neither of which
# is part of the actual summary, so both are stripped here (a no-op if
# either pattern isn't present).
function Format-NoteContent {
  param([object]$Note, [string]$NoteType)
  $body = Get-RawNoteBody -Note $Note
  if ($NoteType -eq "Meeting") {
    $body = $body -replace '(?ims)\r?\n-{3,}\s*\r?\nChat with meeting transcript:.*$', ''
    $body = $body -replace '(?im)^Added by:.*\r?\n?', ''
    $body = $body.Trim()
  }
  $title = [string]$Note.title
  if ([string]::IsNullOrWhiteSpace($title)) { return $body }
  if ($body.TrimStart().StartsWith($title)) { return $body }
  if ([string]::IsNullOrWhiteSpace($body)) { return $title }
  return "# $title`n`n$body"
}

# Parallelizes the one-native-notes-call-per-record fan-out (the real
# bottleneck: ~3,200 Companies + ~4,500 People = ~7,700 sequential GET
# calls otherwise). Everything else in this script (idempotency map, record
# creation) stays single-threaded -- only this read-only fetch is safe and
# worthwhile to run concurrently. Each runspace duplicates the retry logic
# from `Request` above (functions in the parent scope aren't visible inside
# a runspace) rather than sharing it, so keep the two in sync if either
# changes.
function Get-NativeNotesParallel {
  param([array]$Records, [string]$ParentObject, [hashtable]$Headers, [int]$Workers)

  $scriptBlock = {
    param($NativeId, $OrgId, $PersonId, $ParentObject, $Headers)
    function Request {
      param([string]$Path)
      for ($attempt = 1; $attempt -le 8; $attempt++) {
        try {
          return Invoke-RestMethod -Method Get -Uri "https://api.attio.com/v2$Path" -Headers $Headers
        } catch {
          $status = 0
          if ($_.Exception.Response) { $status = [int]$_.Exception.Response.StatusCode }
          if ($attempt -eq 8 -or ($status -ne 429 -and $status -lt 500)) { throw }
          Start-Sleep -Seconds ([Math]::Min(60, 5 * $attempt))
        }
      }
    }
    $items = [Collections.Generic.List[object]]::new()
    $offset = 0
    while ($true) {
      $page = @((Request "/notes?parent_object=$ParentObject&parent_record_id=$NativeId&limit=50&offset=$offset").data)
      $items.AddRange($page)
      if ($page.Count -lt 50) { break }
      $offset += 50
    }
    [pscustomobject]@{ OrgId = $OrgId; PersonId = $PersonId; Notes = $items }
  }

  $pool = [runspacefactory]::CreateRunspacePool(1, $Workers)
  $pool.Open()
  $jobs = [Collections.Generic.List[object]]::new()
  foreach ($r in $Records) {
    $ps = [powershell]::Create()
    $ps.RunspacePool = $pool
    [void]$ps.AddScript($scriptBlock).AddArgument($r.NativeId).AddArgument($r.OrgId).AddArgument($r.PersonId).AddArgument($ParentObject).AddArgument($Headers)
    $jobs.Add([pscustomobject]@{ PS = $ps; Handle = $ps.BeginInvoke() })
  }

  $results = [Collections.Generic.List[object]]::new()
  $done = 0
  foreach ($job in $jobs) {
    try {
      $results.Add($job.PS.EndInvoke($job.Handle))
    } catch {
      Write-Warning "A note fetch failed: $($_.Exception.Message)"
    }
    $job.PS.Dispose()
    $done++
    if ($done % 250 -eq 0) { Write-Host "  ...$done/$($jobs.Count) scanned" }
  }
  $pool.Close()
  $pool.Dispose()
  return $results
}

Write-Host ""
Write-Host "Fetching native Companies to read their Notes panel..."
$companies = Get-AllRecords -ObjectSlug "companies"
if ($Limit -gt 0) { $companies = @($companies | Select-Object -First $Limit) }
Write-Host "Native Companies: $($companies.Count)."

$companiesSkippedNoOrg = 0
$companyFetchList = [Collections.Generic.List[object]]::new()
foreach ($c in $companies) {
  $nativeId = [string]$c.id.record_id
  if (-not $orgByLegacyId.ContainsKey($nativeId)) { $companiesSkippedNoOrg++; continue }
  $companyFetchList.Add([pscustomobject]@{ NativeId = $nativeId; OrgId = $orgByLegacyId[$nativeId]; PersonId = $null })
}
Write-Host "Companies to fetch notes for: $($companyFetchList.Count) (skipped, not yet migrated to organizations: $companiesSkippedNoOrg). Using $Workers worker(s)..."
$companyResults = Get-NativeNotesParallel -Records $companyFetchList -ParentObject "companies" -Headers $headers -Workers $Workers

$companyNoteCount = 0
$companyMeetingCount = 0
foreach ($result in $companyResults) {
  foreach ($n in $result.Notes) {
    $noteId = [string]$n.id.note_id
    $noteType = Get-NoteType -Note $n
    $content = Format-NoteContent -Note $n -NoteType $noteType
    if ($noteType -eq "Meeting") { $companyMeetingCount++ }
    Add-Note -LegacyNoteId "note:$noteId" -OrganizationId $result.OrgId -PersonId $null -BuyerRoleId $null -Content $content -CreatedAt ([string]$n.created_at) -NoteType $noteType
    $companyNoteCount++
  }
}
Write-Host "Company native notes found: $companyNoteCount (Meeting: $companyMeetingCount, Manual: $($companyNoteCount - $companyMeetingCount))."

Write-Host ""
Write-Host "Fetching native People to read their Notes panel..."
$people = Get-AllRecords -ObjectSlug "people"
if ($Limit -gt 0) { $people = @($people | Select-Object -First $Limit) }
Write-Host "Native People: $($people.Count)."

$peopleSkippedNoPerson = 0
$peopleNoOrg = 0
$personFetchList = [Collections.Generic.List[object]]::new()
foreach ($p in $people) {
  $nativeId = [string]$p.id.record_id
  if (-not $personByLegacyId.ContainsKey($nativeId)) { $peopleSkippedNoPerson++; continue }
  $personId = $personByLegacyId[$nativeId]
  $orgId = $null
  if ($personOrgId.ContainsKey($personId)) { $orgId = $personOrgId[$personId] } else { $peopleNoOrg++ }
  $personFetchList.Add([pscustomobject]@{ NativeId = $nativeId; OrgId = $orgId; PersonId = $personId })
}
Write-Host "People to fetch notes for: $($personFetchList.Count) (skipped, not yet migrated to person: $peopleSkippedNoPerson; no linked organization, migrating with organization_id blank: $peopleNoOrg). Using $Workers worker(s)..."
$personResults = Get-NativeNotesParallel -Records $personFetchList -ParentObject "people" -Headers $headers -Workers $Workers

$personNoteCount = 0
$personMeetingCount = 0
foreach ($result in $personResults) {
  foreach ($n in $result.Notes) {
    $noteId = [string]$n.id.note_id
    $noteType = Get-NoteType -Note $n
    $content = Format-NoteContent -Note $n -NoteType $noteType
    if ($noteType -eq "Meeting") { $personMeetingCount++ }
    Add-Note -LegacyNoteId "note:$noteId" -OrganizationId $result.OrgId -PersonId $result.PersonId -BuyerRoleId $null -Content $content -CreatedAt ([string]$n.created_at) -NoteType $noteType
    $personNoteCount++
  }
}
Write-Host "Person native notes found: $personNoteCount (Meeting: $personMeetingCount, Manual: $($personNoteCount - $personMeetingCount))."

Write-Host ""
Write-Host "Fetching buyer_role list entries for their notes field..."
$buyerRoleEntries = [Collections.Generic.List[object]]::new()
$offset = 0
while ($true) {
  $page = @((Request Post "/lists/buyer_role/entries/query" @{ limit = 500; offset = $offset }).data)
  $buyerRoleEntries.AddRange($page)
  if ($page.Count -lt 500) { break }
  $offset += 500
}
if ($Limit -gt 0) { $buyerRoleEntries = @($buyerRoleEntries | Select-Object -First $Limit) }
Write-Host "Buyer Role entries: $($buyerRoleEntries.Count)."

$buyerRoleNoteCount = 0
foreach ($e in $buyerRoleEntries) {
  $entryId = if ($e.id.entry_id) { [string]$e.id.entry_id } else { [string]$e.entry_id }
  $orgId = if ($e.parent_record_id.record_id) { [string]$e.parent_record_id.record_id } elseif ($e.parent_record_id) { [string]$e.parent_record_id } else { $null }
  $content = Get-Value -Values $e.entry_values -Slug "notes"
  if (-not $orgId -or [string]::IsNullOrWhiteSpace($content)) { continue }
  Add-Note -LegacyNoteId "buyer_role:$entryId" -OrganizationId $orgId -PersonId $null -BuyerRoleId $entryId -Content $content -CreatedAt $null -NoteType "Manual"
  $buyerRoleNoteCount++
}
Write-Host "Buyer Role notes found: $buyerRoleNoteCount."

# --- 4. Report + apply -------------------------------------------------------

Write-Host ""
$manualCount = @($toCreate | Where-Object { $_.NoteType -eq "Manual" }).Count
$meetingCount = @($toCreate | Where-Object { $_.NoteType -eq "Meeting" }).Count
Write-Host "Total new Notes records to create: $($toCreate.Count) (Manual: $manualCount, Meeting: $meetingCount)."
foreach ($sample in @($toCreate | Select-Object -First 5)) {
  $preview = if ($sample.Content.Length -gt 80) { $sample.Content.Substring(0, 80) + "..." } else { $sample.Content }
  Write-Host "  SAMPLE: $($sample.LegacyNoteId) [$($sample.NoteType)] org=$($sample.OrganizationId) person=$($sample.PersonId) content=`"$preview`""
}
Write-Host "Total existing Notes records to update (SOURCE content changed since they were created): $($toUpdate.Count)."
foreach ($sample in @($toUpdate | Select-Object -First 5)) {
  $preview = if ($sample.Content.Length -gt 80) { $sample.Content.Substring(0, 80) + "..." } else { $sample.Content }
  Write-Host "  SAMPLE: $($sample.LegacyNoteId) [$($sample.NoteType)] content=`"$preview`""
}

if (-not $Apply) {
  Write-Host ""
  Write-Host "Dry run complete. Add -Apply -Confirmation APPLY_NOTES_BACKFILL_TO_SOURCE to write these $($toCreate.Count) new + $($toUpdate.Count) updated records."
  exit 0
}

function Build-NoteValues {
  param([object]$Item, [bool]$HasNameAttribute)
  $values = @{
    note_type = $Item.NoteType
    content   = $Item.Content
  }
  if ($Item.OrganizationId) { $values.organization_id = @{ target_object = "organizations"; target_record_id = $Item.OrganizationId } }
  if ($Item.PersonId) { $values.person_id = @{ target_object = "person"; target_record_id = $Item.PersonId } }
  if ($Item.BuyerRoleId) { $values.buyer_role_id = $Item.BuyerRoleId }
  if ($Item.CreatedAt) { $values.note_created_at = $Item.CreatedAt }
  # The default "Name" attribute every custom object gets is Attio's record
  # label -- left unset by every other field above, so give it something
  # short and identifying rather than risk a 400 if it turns out required.
  if ($HasNameAttribute) {
    $values.name = if ($Item.Content.Length -gt 60) { $Item.Content.Substring(0, 60) + "..." } else { $Item.Content }
  }
  return $values
}

$hasNameAttribute = $attrs.ContainsKey("name")
$created = 0
foreach ($item in $toCreate) {
  $values = Build-NoteValues -Item $item -HasNameAttribute $hasNameAttribute
  $values.legacy_note_id = $item.LegacyNoteId
  try {
    Request Post "/objects/note/records" @{ data = @{ values = $values } } | Out-Null
    $created++
  } catch {
    $message = if ($_.ErrorDetails.Message) { $_.ErrorDetails.Message } else { $_.Exception.Message }
    Write-Warning "FAILED to create note $($item.LegacyNoteId): $message"
  }
}
$updated = 0
foreach ($item in $toUpdate) {
  $values = Build-NoteValues -Item $item -HasNameAttribute $hasNameAttribute
  try {
    Request Put "/objects/note/records/$($item.RecordId)" @{ data = @{ values = $values } } | Out-Null
    $updated++
  } catch {
    $message = if ($_.ErrorDetails.Message) { $_.ErrorDetails.Message } else { $_.Exception.Message }
    Write-Warning "FAILED to update note $($item.LegacyNoteId): $message"
  }
}
Write-Host "Backfill complete. Created $created / $($toCreate.Count). Updated $updated / $($toUpdate.Count)."
