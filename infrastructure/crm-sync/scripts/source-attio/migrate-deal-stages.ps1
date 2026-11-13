param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [ValidateSet("plan", "schema", "records", "archive")]
  [string]$Phase = "plan",
  [ValidateRange(0, 1000000)]
  [int]$Limit = 0,
  [string]$Confirmation,
  [switch]$Apply,
  [switch]$SkipWebhookPause
)

# AZM-169: collapses Deal_V2 `deal_stage` from 20 values to 10 and moves the
# outcome (On hold, Passed, Lost) into a new `deal_status` select.
#
# Phases, run in order, each a dry run unless -Apply:
#   plan     read-only report: per-deal CSV + counts per mapping row
#   schema   create deal_status, rename 1:1 stages in place, create Outreach
#   records  pause the webhook, set stage + status per deal, resume
#   archive  archive the 11 old stages once no deal uses them
#
# Renames keep the status id, so Attio's stage history (days-in-stage) survives.
# Records are compared against their target and skipped when equal, so every
# phase is safe to re-run.
#
# The webhook is paused during `records`: moving a Passed deal back to its last
# real stage would otherwise write a fake stage change into deal_stage_events.
# Postgres catches up through a manual full resync afterwards (it writes no
# stage events).

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($SourceApiKey)) {
  $SourceApiKey = [Environment]::GetEnvironmentVariable("SOURCE_ATTIO_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($SourceApiKey)) { throw "Missing SOURCE_ATTIO_API_KEY." }

if ($Apply) {
  if ($Phase -eq "plan") { throw "-Apply has no meaning for -Phase plan." }
  $phaseToken = "APPLY_DEAL_STAGES_$($Phase.ToUpperInvariant())"
  $isBoundedApply = $Phase -eq "records" -and $Limit -ge 1 -and $Limit -le 10 -and $Confirmation -eq $phaseToken
  $isFullApply = $Limit -eq 0 -and $Confirmation -eq $phaseToken
  if (-not $isBoundedApply -and -not $isFullApply) {
    throw "Pass -Confirmation $phaseToken (records also allows -Limit 1-10)."
  }
}

$headers = @{
  Authorization = "Bearer $($SourceApiKey.Trim())"
  Accept = "application/json"
  "Content-Type" = "application/json"
}

$outputRoot = Join-Path $PSScriptRoot "..\..\..\..\outputs\attio_migration"
$null = New-Item -ItemType Directory -Force -Path $outputRoot

$stagePath = "/objects/deal/attributes/deal_stage"
$statusPath = "/objects/deal/attributes/deal_status"

# The spec's 10 stages, in pipeline order.
$newStages = @(
  "Lead", "Qualified", "Engaged", "Mandate signed", "Preparation", "Outreach",
  "Non-binding offers", "Due diligence", "Closing", "Closed"
)
$newStatuses = @("Active", "On hold", "Passed", "Lost")

# Old title -> new title for live stages. New titles map to themselves so a
# re-run, and history read after the renames, resolve the same way.
$stageMap = @{
  "Inbound" = "Lead"
  "Qualified" = "Qualified"; "Screened" = "Qualified"
  "Engaged" = "Engaged"
  "Mandate Signed" = "Mandate signed"; "(Buyer) Mandate Active" = "Mandate signed"
  "Teaser/Data Room In Progress" = "Preparation"
  "Teaser Distributed" = "Outreach"; "NDA Circulated" = "Outreach"
  "NDA Signed" = "Outreach"; "CIM Distributed" = "Outreach"
  "LOI Received" = "Non-binding offers"
  "LOI signed/Due Diligence" = "Due diligence"; "Exclusivity" = "Due diligence"
  "Offer Signed/ Legal Docs" = "Closing"
  "Closed" = "Closed"
  # Already-archived statuses that can still appear in a deal's history.
  "Mandate Active" = "Mandate signed"
  "Due Diligence (archived)" = "Due diligence"
}
foreach ($title in $newStages) { $stageMap[$title] = $title }

# Outcome stages: the deal keeps its last real stage and gets this status.
$terminalStatus = @{ "On Hold" = "On hold"; "Passed" = "Passed"; "Lost" = "Lost"; "Failed" = "Lost" }

# Renamed in place (same status id), so history follows the deal.
$renames = [ordered]@{
  "Inbound" = "Lead"
  "Mandate Signed" = "Mandate signed"
  "Teaser/Data Room In Progress" = "Preparation"
  "LOI Received" = "Non-binding offers"
  "LOI signed/Due Diligence" = "Due diligence"
  "Offer Signed/ Legal Docs" = "Closing"
}
$toArchive = @(
  "Screened", "(Buyer) Mandate Active", "Teaser Distributed", "NDA Circulated", "NDA Signed",
  "CIM Distributed", "Exclusivity", "Passed", "On Hold", "Lost", "Failed"
)

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

function Get-CurrentTitle {
  param([object]$Values, [string]$Slug)
  $item = @($Values.$Slug) | Where-Object { $null -eq $_.active_until } | Select-Object -First 1
  if ($null -eq $item) { return $null }
  if ($item.status.title) { return [string]$item.status.title }
  if ($item.option.title) { return [string]$item.option.title }
  if ($null -ne $item.value) { return [string]$item.value }
  return $null
}

function Get-StageStatusList {
  return @((Invoke-AttioRequest -Method Get -Path "$stagePath/statuses?show_archived=true").data)
}

function Get-DealStatusOptionList {
  try {
    return @((Invoke-AttioRequest -Method Get -Path "$statusPath/options?show_archived=true").data)
  } catch {
    if ([int]$_.Exception.Response.StatusCode -eq 404) { return $null }
    throw
  }
}

# Newest earlier stage that maps to a live one; Lead when the deal never had one.
function Get-LastRealStage {
  param([string]$RecordId)
  $history = @((Invoke-AttioRequest -Method Get `
    -Path "/objects/deal/records/$RecordId/attributes/deal_stage/values?show_historic=true").data)
  $ordered = $history | Sort-Object { [DateTime]$_.active_from } -Descending
  foreach ($value in $ordered) {
    $title = [string]$value.status.title
    if ($stageMap.ContainsKey($title)) {
      return @{ stage = $stageMap[$title]; from = $title }
    }
  }
  return @{ stage = "Lead"; from = "" }
}

$decisions = Get-Content (Join-Path $PSScriptRoot "config\migration-decisions.json") -Raw |
  ConvertFrom-Json
$expectedWorkspaceId = [string]$decisions.workspace_id
$organizationsObject = Invoke-AttioRequest -Method Get -Path "/objects/organizations"
$connectedWorkspaceId = [string]$organizationsObject.data.id.workspace_id
if ($connectedWorkspaceId -ne $expectedWorkspaceId) {
  throw "Workspace mismatch. Expected $expectedWorkspaceId but connected to $connectedWorkspaceId."
}

# --- schema -------------------------------------------------------------------

if ($Phase -eq "schema") {
  $actions = [Collections.Generic.List[string]]::new()

  $options = Get-DealStatusOptionList
  if ($null -eq $options) {
    $actions.Add("create attribute deal_status (select)")
    if ($Apply) {
      Invoke-AttioRequest -Method Post -Path "/objects/deal/attributes" -Body @{
        data = @{
          title = "Deal status"; description = "Whether the deal is still alive. Set with deal_stage."
          api_slug = "deal_status"; type = "select"; is_required = $false; is_unique = $false
          is_multiselect = $false; config = @{}
        }
      } | Out-Null
      $options = @()
    } else { $options = @() }
  }
  foreach ($title in $newStatuses) {
    $existing = $options | Where-Object { $_.title -ceq $title } | Select-Object -First 1
    if ($null -eq $existing) {
      $actions.Add("create deal_status option '$title'")
      if ($Apply) {
        Invoke-AttioRequest -Method Post -Path "$statusPath/options" -Body @{ data = @{ title = $title } } | Out-Null
      }
    } elseif ($existing.is_archived) {
      $actions.Add("unarchive deal_status option '$title'")
      if ($Apply) {
        Invoke-AttioRequest -Method Patch -Path "$statusPath/options/$($existing.id.option_id)" `
          -Body @{ data = @{ is_archived = $false } } | Out-Null
      }
    }
  }

  # Titles compare case-sensitively: "Mandate Signed" -> "Mandate signed" is a real rename.
  $statuses = Get-StageStatusList
  foreach ($old in $renames.Keys) {
    $new = $renames[$old]
    $source = $statuses | Where-Object { -not $_.is_archived -and $_.title -ceq $old } | Select-Object -First 1
    $target = $statuses | Where-Object { -not $_.is_archived -and $_.title -ceq $new } | Select-Object -First 1
    if ($null -ne $target) { continue }
    if ($null -eq $source) { throw "deal_stage has neither '$old' nor '$new'." }
    # An archived status like "Due Diligence" would clash with the new title.
    $clash = $statuses | Where-Object {
      $_.is_archived -and $_.title -eq $new -and $_.id.status_id -ne $source.id.status_id
    } | Select-Object -First 1
    if ($null -ne $clash) {
      $actions.Add("rename archived deal_stage '$($clash.title)' -> '$($clash.title) (archived)'")
      if ($Apply) {
        Invoke-AttioRequest -Method Patch -Path "$stagePath/statuses/$($clash.id.status_id)" `
          -Body @{ data = @{ title = "$($clash.title) (archived)" } } | Out-Null
      }
    }
    $actions.Add("rename deal_stage '$old' -> '$new'")
    if ($Apply) {
      Invoke-AttioRequest -Method Patch -Path "$stagePath/statuses/$($source.id.status_id)" `
        -Body @{ data = @{ title = $new } } | Out-Null
    }
  }
  $outreach = $statuses | Where-Object { $_.title -ceq "Outreach" } | Select-Object -First 1
  if ($null -eq $outreach) {
    $actions.Add("create deal_stage 'Outreach'")
    if ($Apply) {
      Invoke-AttioRequest -Method Post -Path "$stagePath/statuses" -Body @{ data = @{ title = "Outreach" } } | Out-Null
    }
  } elseif ($outreach.is_archived) {
    $actions.Add("unarchive deal_stage 'Outreach'")
    if ($Apply) {
      Invoke-AttioRequest -Method Patch -Path "$stagePath/statuses/$($outreach.id.status_id)" `
        -Body @{ data = @{ is_archived = $false } } | Out-Null
    }
  }

  $mode = if ($Apply) { "APPLIED" } else { "DRY RUN" }
  if ($actions.Count -eq 0) { Write-Host "Schema already migrated. Nothing to do." }
  foreach ($action in $actions) { Write-Host "${mode}: $action" }
  Write-Host "Stage order is not set by the API: drag the 10 stages into spec order in the Attio UI."
  exit 0
}

# --- archive ------------------------------------------------------------------

if ($Phase -eq "archive") {
  $records = Get-PagedData -Path "/objects/deal/records/query"
  $inUse = @{}
  foreach ($record in $records) {
    $title = Get-CurrentTitle -Values $record.values -Slug "deal_stage"
    if ($title) { $inUse[$title] = 1 + [int]$inUse[$title] }
  }
  $statuses = Get-StageStatusList
  foreach ($title in $toArchive) {
    $status = $statuses | Where-Object { $_.title -ceq $title } | Select-Object -First 1
    if ($null -eq $status -or $status.is_archived) { continue }
    if ($inUse.ContainsKey($title)) {
      throw "'$title' is still used by $($inUse[$title]) deal(s). Run -Phase records -Apply first."
    }
    if ($Apply) {
      Invoke-AttioRequest -Method Patch -Path "$stagePath/statuses/$($status.id.status_id)" `
        -Body @{ data = @{ is_archived = $true } } | Out-Null
      Write-Host "APPLIED: archived '$title'"
    } else { Write-Host "DRY RUN: would archive '$title'" }
  }
  exit 0
}

# --- plan / records -----------------------------------------------------------

Write-Host "Reading Deal_V2 records..."
$records = Get-PagedData -Path "/objects/deal/records/query"

$plans = [Collections.Generic.List[object]]::new()
$unplaceable = [Collections.Generic.List[object]]::new()
foreach ($record in $records) {
  $recordId = [string]$record.id.record_id
  $oldStage = Get-CurrentTitle -Values $record.values -Slug "deal_stage"
  $oldStatus = Get-CurrentTitle -Values $record.values -Slug "deal_status"
  $isTest = [bool](Get-CurrentTitle -Values $record.values -Slug "is_test" | Where-Object { $_ -eq "True" })
  $row = [ordered]@{
    record_id = $recordId
    name = Get-CurrentTitle -Values $record.values -Slug "deal_name"
    is_test = $isTest
    old_stage = $oldStage
    old_status = $oldStatus
    history_stage = ""
    new_stage = ""
    new_status = ""
    change = $false
  }
  if ($terminalStatus.ContainsKey([string]$oldStage)) {
    $last = Get-LastRealStage -RecordId $recordId
    $row.history_stage = if ($last.from) { $last.from } else { "(none)" }
    $row.new_stage = $last.stage
    $row.new_status = $terminalStatus[$oldStage]
  } elseif ($stageMap.ContainsKey([string]$oldStage)) {
    $row.new_stage = $stageMap[$oldStage]
    $row.new_status = if ($oldStatus) { $oldStatus } else { "Active" }
  } else {
    $unplaceable.Add($row)
    continue
  }
  $row.change = ($row.new_stage -cne $oldStage) -or ($row.new_status -cne $oldStatus)
  $plans.Add($row)
}

$counts = $plans | Group-Object { "$($_.old_stage) -> $($_.new_stage) / $($_.new_status)" } |
  Sort-Object Name | ForEach-Object { [ordered]@{ mapping = $_.Name; deals = $_.Count } }
$toWrite = @($plans | Where-Object { $_.change })

$stamp = [DateTime]::UtcNow.ToString("yyyyMMdd-HHmmss")
$csvPath = Join-Path $outputRoot "deal-stage-plan-$stamp.csv"
$plans | ForEach-Object { [pscustomobject]$_ } | Export-Csv -Path $csvPath -NoTypeInformation -Encoding UTF8

if ($Phase -eq "records" -and $Apply) {
  if ($unplaceable.Count -gt 0) { throw "$($unplaceable.Count) deal(s) cannot be placed; see the plan." }
  $liveTitles = @(Get-StageStatusList | Where-Object { -not $_.is_archived } | ForEach-Object { [string]$_.title })
  $missing = @($newStages | Where-Object { $liveTitles -cnotcontains $_ })
  $statusOptions = Get-DealStatusOptionList
  if ($missing.Count -gt 0 -or $null -eq $statusOptions) { throw "Run -Phase schema -Apply first." }

  if ($Limit -gt 0) { $toWrite = @($toWrite | Select-Object -First $Limit) }

  $webhook = $null
  if (-not $SkipWebhookPause) {
    $webhooks = @((Invoke-AttioRequest -Method Get -Path "/webhooks").data)
    if ($webhooks.Count -ne 1) {
      throw "$($webhooks.Count) Attio webhooks registered; pause the prod one by hand and pass -SkipWebhookPause."
    }
    $webhook = $webhooks[0]
    [IO.File]::WriteAllText((Join-Path $outputRoot "deal-stage-webhook-backup-$stamp.json"),
      ($webhook | ConvertTo-Json -Depth 20), [Text.UTF8Encoding]::new($false))
    Write-Host "Pausing Attio webhook $($webhook.id.webhook_id)..."
    Invoke-AttioRequest -Method Patch -Path "/webhooks/$($webhook.id.webhook_id)" -Body @{
      data = @{ target_url = $webhook.target_url; subscriptions = @() }
    } | Out-Null
  }

  $written = 0
  $failed = 0
  try {
    foreach ($row in $toWrite) {
      try {
        Invoke-AttioRequest -Method Patch -Path "/objects/deal/records/$($row.record_id)" -Body @{
          data = @{ values = @{ deal_stage = $row.new_stage; deal_status = $row.new_status } }
        } | Out-Null
        $written++
      } catch {
        Write-Warning "failed $($row.record_id): $($_.Exception.Message)"
        $failed++
      }
    }
  } finally {
    if ($null -ne $webhook) {
      try {
        Write-Host "Resuming Attio webhook $($webhook.id.webhook_id)..."
        Invoke-AttioRequest -Method Patch -Path "/webhooks/$($webhook.id.webhook_id)" -Body @{
          data = @{ target_url = $webhook.target_url; subscriptions = $webhook.subscriptions }
        } | Out-Null
      } catch {
        Write-Warning "COULD NOT RESUME the Attio webhook: $($_.Exception.Message)"
        Write-Warning "Restore its subscriptions from deal-stage-webhook-backup-$stamp.json by hand."
      }
    }
  }
  Write-Host "Wrote $written deal(s); $failed failed. Run a full resync so Postgres follows."
  if ($failed -gt 0) { exit 1 }
  exit 0
}

$summary = [ordered]@{
  generated_at_utc = [DateTime]::UtcNow.ToString("o")
  phase = $Phase
  deals = $records.Count
  to_write = $toWrite.Count
  already_migrated = $plans.Count - $toWrite.Count
  unplaceable = $unplaceable.Count
}
$summary | Format-List
$counts | ForEach-Object { [pscustomobject]$_ } | Format-Table -AutoSize
if ($unplaceable.Count -gt 0) {
  Write-Host "Cannot place:"
  $unplaceable | ForEach-Object { [pscustomobject]$_ } | Format-Table record_id, name, old_stage -AutoSize
}
Write-Host "Plan CSV: $csvPath"
