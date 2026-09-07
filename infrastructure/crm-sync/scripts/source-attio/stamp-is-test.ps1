param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [ValidateSet("organizations", "person", "deal", "note", "buyer_role", "seller_role")]
  [string[]]$Entities = @("organizations", "person", "deal", "note", "buyer_role", "seller_role"),
  [int]$Limit = 0,
  [switch]$Apply,
  [string]$Confirmation,
  [switch]$SkipWebhookPause
)

# One-off backfill: stamp is_test = false on every SOURCE record that has no
# is_test value at all.
#
# One SOURCE workspace has served both environments since 2026-09-07, split by
# the is_test checkbox. Every record migrated before that date has the
# attribute but no value, and Attio's UI filter chips offer only "is true" and
# "is false" -- no "is empty" -- so an unstamped record is invisible in both
# environments' saved views.
#
# This is NOT urgent and nothing is broken without it: the REST API's
# `is_test eq false` filter does match unset records, and the sync scripts and
# the webhook skip only an explicit true. What this unblocks is humans
# filtering in the Attio UI, and `-StrictIsTest` on
# server/scripts/postgres-sync/prod/sync-source-to-prod.ps1.
#
# Deliberately NOT done with `sync-all-within-source.ps1 -Apply`, which would
# also have worked: that re-runs the whole migration, layering every mapped
# field (lead_source, is_active, ...) back over each record from SOURCE's
# native objects. It would clobber every manual Attio edit made since
# 2026-08-26 and refire the SOURCE->prod webhook for thousands of records.
# This script writes exactly one attribute and touches nothing else.
#
# Idempotent: only records with no is_test value are selected, so a re-run
# after a completed run finds nothing. Records already stamped -- either
# value -- are never touched, so a dev's is_test = true records are safe.

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($SourceApiKey)) {
  $SourceApiKey = [Environment]::GetEnvironmentVariable("SOURCE_ATTIO_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($SourceApiKey)) { throw "Missing SOURCE_ATTIO_API_KEY." }

$expectedConfirmation = "STAMP_IS_TEST_FALSE_IN_SOURCE"
if ($Apply -and $Confirmation -ne $expectedConfirmation) {
  throw "-Apply requires -Confirmation $expectedConfirmation."
}

$headers = @{
  Authorization  = "Bearer $($SourceApiKey.Trim())"
  Accept         = "application/json"
  "Content-Type" = "application/json"
}

function Request {
  param([ValidateSet("Get", "Post", "Patch")][string]$Method, [string]$Path, [object]$Body)
  $p = @{ Method = $Method; Uri = "https://api.attio.com/v2$Path"; Headers = $headers }
  if ($null -ne $Body) { $p.Body = [Text.Encoding]::UTF8.GetBytes(($Body | ConvertTo-Json -Depth 20)) }
  Invoke-RestMethod @p
}

# Objects and lists differ in three ways at once -- the query path, the
# per-record write path, and whether values live under `values` or
# `entry_values` -- so each entity carries all three rather than the caller
# branching on kind at every use.
$entityConfig = @{
  organizations = @{ Query = "/objects/organizations/records/query"; Write = "/objects/organizations/records"; ValuesKey = "values"; WriteKey = "values" }
  person        = @{ Query = "/objects/person/records/query"; Write = "/objects/person/records"; ValuesKey = "values"; WriteKey = "values" }
  deal          = @{ Query = "/objects/deal/records/query"; Write = "/objects/deal/records"; ValuesKey = "values"; WriteKey = "values" }
  note          = @{ Query = "/objects/note/records/query"; Write = "/objects/note/records"; ValuesKey = "values"; WriteKey = "values" }
  buyer_role    = @{ Query = "/lists/buyer_role/entries/query"; Write = "/lists/buyer_role/entries"; ValuesKey = "entry_values"; WriteKey = "entry_values" }
  seller_role   = @{ Query = "/lists/seller_role/entries/query"; Write = "/lists/seller_role/entries"; ValuesKey = "entry_values"; WriteKey = "entry_values" }
}

$decisions = Get-Content (Join-Path $PSScriptRoot "config\migration-decisions.json") -Raw | ConvertFrom-Json
$expectedWorkspaceId = [string]$decisions.workspace_id
$connectedWorkspaceId = [string](Request Get "/objects/organizations" $null).data.id.workspace_id
if ($connectedWorkspaceId -ne $expectedWorkspaceId) {
  throw "Workspace mismatch. Expected $expectedWorkspaceId but connected to $connectedWorkspaceId."
}
Write-Host "Connected to workspace $connectedWorkspaceId."

function Get-RecordId {
  param([object]$Record)
  if ($Record.id.record_id) { return [string]$Record.id.record_id }
  if ($Record.id.entry_id) { return [string]$Record.id.entry_id }
  return $null
}

# "No value" means no *active* value entry. A superseded one (active_until
# set) does not count as stamped -- the same rule values.py's `raw_items` and
# the sync scripts' `items()` apply on the read side.
function Test-IsTestUnset {
  param([object]$Record, [string]$ValuesKey)
  $items = @($Record.$ValuesKey.is_test | Where-Object { -not $_.active_until })
  return $items.Count -eq 0
}

function Get-IsTestValue {
  param([object]$Record, [string]$ValuesKey)
  $items = @($Record.$ValuesKey.is_test | Where-Object { -not $_.active_until })
  if ($items.Count -eq 0) { return $null }
  return [bool]$items[0].value
}

function Get-AllRecords {
  param([string]$Path)
  $all = [Collections.Generic.List[object]]::new()
  $offset = 0
  while ($true) {
    $page = @((Request Post $Path @{ limit = 500; offset = $offset }).data)
    if ($page.Count -gt 0) { $all.AddRange($page) }
    if ($page.Count -lt 500) { break }
    $offset += 500
  }
  return $all
}

# --- survey every requested entity before writing anything -------------------

$plan = [ordered]@{}
foreach ($entity in $Entities) {
  $config = $entityConfig[$entity]
  $valuesKey = [string]$config.ValuesKey
  Write-Host "Reading $entity..."
  $records = Get-AllRecords ([string]$config.Query)
  $unset = @($records | Where-Object { Test-IsTestUnset $_ $valuesKey })
  $stampedTrue = @($records | Where-Object { (Get-IsTestValue $_ $valuesKey) -eq $true }).Count
  $stampedFalse = $records.Count - $unset.Count - $stampedTrue
  if ($Limit -gt 0 -and $unset.Count -gt $Limit) { $unset = @($unset[0..($Limit - 1)]) }
  $plan[$entity] = @{ Config = $config; ToStamp = $unset; Total = $records.Count; True = $stampedTrue; False = $stampedFalse }
}

Write-Host ""
Write-Host ("{0,-14} {1,8} {2,10} {3,10} {4,10}" -f "Entity", "total", "is_test=t", "is_test=f", "to stamp")
Write-Host ("-" * 56)
$totalToStamp = 0
foreach ($entity in $plan.Keys) {
  $row = $plan[$entity]
  $totalToStamp += $row.ToStamp.Count
  Write-Host ("{0,-14} {1,8} {2,10} {3,10} {4,10}" -f $entity, $row.Total, $row.True, $row.False, $row.ToStamp.Count)
}
Write-Host ("-" * 56)
Write-Host "Records to stamp is_test = false: $totalToStamp"

if (-not $Apply) {
  Write-Host ""
  Write-Host "Dry run complete. Nothing was written."
  Write-Host "To apply: .\stamp-is-test.ps1 -Apply -Confirmation $expectedConfirmation"
  exit 0
}
if ($totalToStamp -eq 0) {
  Write-Host "Nothing to stamp. Exiting."
  exit 0
}

# --- pause the webhook, stamp, resume ----------------------------------------
#
# Without this, stamping N records fires N webhook deliveries at the prod
# toolkit, each of which re-fetches the record and re-upserts a row whose
# content has not meaningfully changed. Copied from
# sync-all-within-source.ps1's own pause/resume: best-effort by design, since
# failing to pause is far better than aborting a half-finished stamp.

$webhook = $null
$webhookPaused = $false
if (-not $SkipWebhookPause) {
  try {
    $webhooks = @((Request Get "/webhooks" $null).data)
    if ($webhooks.Count -ne 1) {
      Write-Warning "$($webhooks.Count) Attio webhooks registered -- ambiguous which is the prod sync. Continuing without pausing."
    } else {
      $webhook = $webhooks[0]
      Write-Host "Pausing Attio webhook $($webhook.id.webhook_id) for the duration of this run..."
      Request Patch "/webhooks/$($webhook.id.webhook_id)" @{
        data = @{ target_url = $webhook.target_url; subscriptions = @() }
      } | Out-Null
      $webhookPaused = $true
    }
  } catch {
    Write-Warning "Could not pause the Attio webhook ($($_.Exception.Message)) -- continuing without pausing."
    $webhook = $null
    $webhookPaused = $false
  }
}

$stamped = 0
$failed = 0
try {
  foreach ($entity in $plan.Keys) {
    $row = $plan[$entity]
    if ($row.ToStamp.Count -eq 0) { continue }
    Write-Host ""
    Write-Host "===== $entity ($($row.ToStamp.Count) records) ====="
    # Bound to plain variables first: PowerShell mis-parses a property access
    # used as a hashtable literal's key (`@{ $x.Prop = ... }`).
    $writePath = [string]$row.Config.Write
    $writeKey = [string]$row.Config.WriteKey
    foreach ($record in $row.ToStamp) {
      $recordId = Get-RecordId $record
      if (-not $recordId) {
        Write-Warning "  skipped a $entity record with no resolvable id"
        $failed++
        continue
      }
      try {
        Request Patch "$writePath/$recordId" @{ data = @{ $writeKey = @{ is_test = $false } } } | Out-Null
        $stamped++
      } catch {
        Write-Warning "  failed $entity $recordId : $($_.Exception.Message)"
        $failed++
      }
    }
    Write-Host "  done ($stamped stamped so far, $failed failed)"
  }
} finally {
  if ($webhookPaused -and $null -ne $webhook) {
    try {
      Write-Host ""
      Write-Host "Resuming Attio webhook $($webhook.id.webhook_id)..."
      Request Patch "/webhooks/$($webhook.id.webhook_id)" @{
        data = @{ target_url = $webhook.target_url; subscriptions = $webhook.subscriptions }
      } | Out-Null
    } catch {
      Write-Warning "COULD NOT RESUME the Attio webhook: $($_.Exception.Message)"
      Write-Warning "Re-enable its subscriptions by hand before relying on real-time sync again."
    }
  }
}

Write-Host ""
Write-Host "Stamping complete. Stamped $stamped record(s); $failed failed."
if ($failed -gt 0) {
  Write-Host "Re-run to retry the failures -- already-stamped records are skipped."
  exit 1
}
Write-Host "Re-run the dry run to confirm 'to stamp' is 0 everywhere, then enable"
Write-Host "-StrictIsTest on server/scripts/postgres-sync/prod/sync-source-to-prod.ps1."
