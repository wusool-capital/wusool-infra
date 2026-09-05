param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [ValidateRange(1, 16)]
  [int]$Workers = 8
)

# Read-only, independent of backfill-notes.ps1: re-derives the expected set
# of Manual + Meeting notes straight from SOURCE (same three sources, same
# Granola-link classification and content formatting), then compares against
# what actually exists in the `note` object right now -- by legacy_note_id,
# AND by note_type/content for every record present on both sides. A count
# match alone can hide N missing + N unrelated-extra records cancelling out,
# or a record that exists but with the wrong type/content -- this catches
# both, not just presence.
#
# Writes nothing. Safe to run any time, including mid-backfill.

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($SourceApiKey)) {
  $SourceApiKey = [Environment]::GetEnvironmentVariable("SOURCE_ATTIO_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($SourceApiKey)) { throw "Missing SOURCE_ATTIO_API_KEY." }

$headers = @{
  Authorization  = "Bearer $($SourceApiKey.Trim())"
  Accept         = "application/json"
  "Content-Type" = "application/json"
}

function Request {
  param([ValidateSet("Get", "Post")][string]$Method, [string]$Path, [object]$Body)
  for ($attempt = 1; $attempt -le 8; $attempt++) {
    try {
      $p = @{ Method = $Method; Uri = "https://api.attio.com/v2$Path"; Headers = $headers }
      if ($null -ne $Body) { $p.Body = [Text.Encoding]::UTF8.GetBytes(($Body | ConvertTo-Json -Depth 20)) }
      return Invoke-RestMethod @p
    } catch {
      $status = 0
      if ($_.Exception.Response) { $status = [int]$_.Exception.Response.StatusCode }
      if ($attempt -eq 8 -or ($status -ne 429 -and $status -lt 500)) { throw }
      Start-Sleep -Seconds ([Math]::Min(60, 5 * $attempt))
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

function Get-RawNoteBody {
  param([object]$Note)
  if ($Note.content_plaintext) { return [string]$Note.content_plaintext }
  return [string]$Note.content_markdown
}

# Same rules as backfill-notes.ps1's Get-NoteType/Format-NoteContent -- must
# stay identical or this validator will disagree with what was actually
# written for reasons that have nothing to do with a real migration bug.
function Get-NoteType {
  param([object]$Note)
  $body = Get-RawNoteBody -Note $Note
  if ($body -match '(?i)granola\.ai|chat with meeting transcript') { return "Meeting" }
  return "Manual"
}

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

function Get-NativeNotesParallel {
  param([array]$RecordIds, [string]$ParentObject, [hashtable]$Headers, [int]$Workers)
  $scriptBlock = {
    param($NativeId, $ParentObject, $Headers)
    function Request {
      param([string]$Path)
      for ($attempt = 1; $attempt -le 8; $attempt++) {
        try { return Invoke-RestMethod -Method Get -Uri "https://api.attio.com/v2$Path" -Headers $Headers }
        catch {
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
    $items
  }
  $pool = [runspacefactory]::CreateRunspacePool(1, $Workers)
  $pool.Open()
  $jobs = [Collections.Generic.List[object]]::new()
  foreach ($id in $RecordIds) {
    $ps = [powershell]::Create(); $ps.RunspacePool = $pool
    [void]$ps.AddScript($scriptBlock).AddArgument($id).AddArgument($ParentObject).AddArgument($Headers)
    $jobs.Add([pscustomobject]@{ PS = $ps; Handle = $ps.BeginInvoke() })
  }
  $results = [Collections.Generic.List[object]]::new()
  $done = 0
  foreach ($job in $jobs) {
    try { $results.AddRange(@($job.PS.EndInvoke($job.Handle))) } catch { Write-Warning "Fetch failed: $($_.Exception.Message)" }
    $job.PS.Dispose()
    $done++
    if ($done % 250 -eq 0) { Write-Host "  ...$done/$($jobs.Count) scanned" }
  }
  $pool.Close(); $pool.Dispose()
  return $results
}

Write-Host "Loading migrated Organizations and People (same eligibility filter as backfill-notes.ps1 -- a note whose parent Company/Person hasn't been migrated yet is not 'missing', it's not eligible)..."
$orgRecords = Get-AllRecords -ObjectSlug "organizations"
$personRecords = Get-AllRecords -ObjectSlug "person"
$orgByLegacyId = @{}
foreach ($r in $orgRecords) {
  $legacy = Get-Value -Values $r.values -Slug "legacy_attio_id"
  if ($legacy) { $orgByLegacyId[$legacy] = $true }
}
$personByLegacyId = @{}
foreach ($r in $personRecords) {
  $legacy = Get-Value -Values $r.values -Slug "legacy_attio_id"
  if ($legacy) { $personByLegacyId[$legacy] = $true }
}

Write-Host "Recomputing expected notes from SOURCE (Companies, People, Buyer Role)..."
$companies = Get-AllRecords -ObjectSlug "companies"
$people = Get-AllRecords -ObjectSlug "people"
$companyIds = @($companies | Where-Object { $orgByLegacyId.ContainsKey([string]$_.id.record_id) } | ForEach-Object { [string]$_.id.record_id })
# A Person is eligible once migrated, whether or not they have a company --
# backfill-notes.ps1 (2026-08-29) migrates person-only notes with
# organization_id left blank instead of skipping them, since some SOURCE
# contacts genuinely have no company on either of SOURCE's own
# company-reference fields.
$personIds = @($people | Where-Object {
    # Not $pid -- collides with PowerShell's reserved, read-only automatic
    # $PID variable (case-insensitive), which is exactly what just broke.
    $recordId = [string]$_.id.record_id
    $personByLegacyId.ContainsKey($recordId)
  } | ForEach-Object { [string]$_.id.record_id })
Write-Host "Eligible (parent already migrated): $($companyIds.Count)/$($companies.Count) companies, $($personIds.Count)/$($people.Count) people."

$companyNotes = Get-NativeNotesParallel -RecordIds $companyIds -ParentObject "companies" -Headers $headers -Workers $Workers
$personNotes = Get-NativeNotesParallel -RecordIds $personIds -ParentObject "people" -Headers $headers -Workers $Workers

$expected = @{}
foreach ($n in $companyNotes) {
  $legacyId = "note:$($n.id.note_id)"
  $noteType = Get-NoteType -Note $n
  $expected[$legacyId] = [pscustomobject]@{ NoteType = $noteType; Content = Format-NoteContent -Note $n -NoteType $noteType }
}
foreach ($n in $personNotes) {
  $legacyId = "note:$($n.id.note_id)"
  $noteType = Get-NoteType -Note $n
  $expected[$legacyId] = [pscustomobject]@{ NoteType = $noteType; Content = Format-NoteContent -Note $n -NoteType $noteType }
}

$buyerRoleEntries = [Collections.Generic.List[object]]::new()
$offset = 0
while ($true) {
  $page = @((Request Post "/lists/buyer_role/entries/query" @{ limit = 500; offset = $offset }).data)
  $buyerRoleEntries.AddRange($page)
  if ($page.Count -lt 500) { break }
  $offset += 500
}
foreach ($e in $buyerRoleEntries) {
  $entryId = if ($e.id.entry_id) { [string]$e.id.entry_id } else { [string]$e.entry_id }
  $content = Get-Value -Values $e.entry_values -Slug "notes"
  if ([string]::IsNullOrWhiteSpace($content)) { continue }
  $expected["buyer_role:$entryId"] = [pscustomobject]@{ NoteType = "Manual"; Content = $content }
}

$expectedManual = @($expected.Values | Where-Object { $_.NoteType -eq "Manual" }).Count
$expectedMeeting = @($expected.Values | Where-Object { $_.NoteType -eq "Meeting" }).Count
Write-Host "Expected in SOURCE right now: $($expected.Count) total (Manual: $expectedManual, Meeting: $expectedMeeting)."

Write-Host ""
Write-Host "Fetching actual 'note' object records from Attio..."
$actualNotes = Get-AllRecords -ObjectSlug "note"
$actual = @{}
foreach ($r in $actualNotes) {
  $legacyId = Get-Value -Values $r.values -Slug "legacy_note_id"
  if ($legacyId) {
    $actual[$legacyId] = [pscustomobject]@{
      NoteType = Get-Value -Values $r.values -Slug "note_type"
      Content  = Get-Value -Values $r.values -Slug "content"
    }
  }
}
$actualManual = @($actual.Values | Where-Object { $_.NoteType -eq "Manual" }).Count
$actualMeeting = @($actual.Values | Where-Object { $_.NoteType -eq "Meeting" }).Count
Write-Host "Actual in 'note' object: $($actual.Count) total (Manual: $actualManual, Meeting: $actualMeeting)."

$missing = @($expected.Keys | Where-Object { -not $actual.ContainsKey($_) })
$missingManual = @($missing | Where-Object { $expected[$_].NoteType -eq "Manual" })
$missingMeeting = @($missing | Where-Object { $expected[$_].NoteType -eq "Meeting" })
$extra = @($actual.Keys | Where-Object { -not $expected.ContainsKey($_) })

# Present on both sides -- now check the DATA matches, not just the id.
$present = @($expected.Keys | Where-Object { $actual.ContainsKey($_) })
$typeMismatches = [Collections.Generic.List[object]]::new()
$contentMismatches = [Collections.Generic.List[object]]::new()
foreach ($id in $present) {
  $exp = $expected[$id]; $act = $actual[$id]
  if ([string]$exp.NoteType -ne [string]$act.NoteType) {
    $typeMismatches.Add([pscustomobject]@{ Id = $id; Expected = $exp.NoteType; Actual = $act.NoteType })
  }
  if ([string]$exp.Content -ne [string]$act.Content) {
    $contentMismatches.Add([pscustomobject]@{ Id = $id })
  }
}

Write-Host ""
Write-Host "===== Counts ====="
$manualMatch = $expectedManual -eq $actualManual
$meetingMatch = $expectedMeeting -eq $actualMeeting
Write-Host "Manual:  expected=$expectedManual actual=$actualManual -> $(if ($manualMatch) { 'MATCH' } else { 'MISMATCH' })"
Write-Host "Meeting: expected=$expectedMeeting actual=$actualMeeting -> $(if ($meetingMatch) { 'MATCH' } else { 'MISMATCH' })"
Write-Host "Total:   expected=$($expected.Count) actual=$($actual.Count) -> $(if ($expected.Count -eq $actual.Count) { 'MATCH' } else { 'MISMATCH' })"
if (-not $manualMatch -or -not $meetingMatch) {
  Write-Host "A count mismatch can still hide equal-and-opposite missing/extra records -- see the missing/extra breakdown below for exactly which ones."
}

Write-Host ""
Write-Host "===== Result ====="
$ok = ($missing.Count -eq 0) -and ($typeMismatches.Count -eq 0) -and ($contentMismatches.Count -eq 0)
if ($ok) {
  Write-Host "PASS: every expected note exists in Attio with matching note_type and content."
} else {
  Write-Host "FAIL:"
}

if ($missing.Count -gt 0) {
  Write-Host "  $($missing.Count) expected note(s) missing entirely (Manual: $($missingManual.Count), Meeting: $($missingMeeting.Count))."
  foreach ($id in @($missingMeeting | Select-Object -First 10)) { Write-Host "    MISSING (Meeting): $id" }
  foreach ($id in @($missingManual | Select-Object -First 10)) { Write-Host "    MISSING (Manual): $id" }
  if ($missing.Count -gt 20) { Write-Host "    ...and $($missing.Count - 20) more." }
}

if ($typeMismatches.Count -gt 0) {
  Write-Host "  $($typeMismatches.Count) note(s) exist but with the wrong note_type."
  foreach ($m in @($typeMismatches | Select-Object -First 10)) { Write-Host "    TYPE MISMATCH: $($m.Id) expected=$($m.Expected) actual=$($m.Actual)" }
}

function Show-Escaped {
  param([string]$Text)
  return $Text.Replace("`r`n", "[CRLF]").Replace("`r", "[CR]").Replace("`n", "[LF]").Replace("`t", "[TAB]")
}

if ($contentMismatches.Count -gt 0) {
  Write-Host "  $($contentMismatches.Count) note(s) exist but with different content than SOURCE currently has."
  foreach ($m in @($contentMismatches | Select-Object -First 10)) {
    $exp = [string]$expected[$m.Id].Content
    $act = [string]$actual[$m.Id].Content
    Write-Host "    CONTENT MISMATCH: $($m.Id) (expected length=$($exp.Length), actual length=$($act.Length))"
    # Find the first index where they actually diverge, so we're not just
    # guessing from a truncated preview -- could be trailing whitespace,
    # a line-ending difference, or genuinely different text.
    $minLen = [Math]::Min($exp.Length, $act.Length)
    $diffAt = -1
    for ($i = 0; $i -lt $minLen; $i++) {
      if ($exp[$i] -ne $act[$i]) { $diffAt = $i; break }
    }
    if ($diffAt -eq -1 -and $exp.Length -ne $act.Length) { $diffAt = $minLen }
    if ($diffAt -eq -1) {
      Write-Host "      Strings compare equal char-by-char up to length $minLen but were flagged different -- investigate directly."
    } else {
      $windowStart = [Math]::Max(0, $diffAt - 20)
      $expWindow = Show-Escaped ($exp.Substring($windowStart, [Math]::Min(50, $exp.Length - $windowStart)))
      $actWindow = Show-Escaped ($act.Substring($windowStart, [Math]::Min(50, $act.Length - $windowStart)))
      Write-Host "      First difference at character $diffAt (of $minLen shared length):"
      Write-Host "        expected: ...`"$expWindow`"..."
      Write-Host "        actual:   ...`"$actWindow`"..."
    }
  }
  Write-Host "    (Note: SOURCE content may have legitimately changed since the backfill ran -- this doesn't always mean a migration bug.)"
}

if ($extra.Count -gt 0) {
  Write-Host "INFO: $($extra.Count) note(s) exist in Attio with a legacy_note_id not matching anything currently in SOURCE (could be legitimate -- content edited/removed in SOURCE since backfill, or created some other way)."
  foreach ($id in @($extra | Select-Object -First 10)) { Write-Host "  EXTRA: $id" }
}
