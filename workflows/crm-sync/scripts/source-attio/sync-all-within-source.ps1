param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [string]$DevApiKey = $env:SOURCE_ATTIO_API_KEY,
  [ValidateSet("organizations", "person", "buyer_role", "seller_role", "deal", "note")]
  [string[]]$Entities = @("organizations", "person", "buyer_role", "seller_role", "deal", "note"),
  [int]$Limit = 0,
  [switch]$Parallel,
  # Upper bound matches backfill-notes.ps1's own ceiling (the highest of any
  # entity here) -- buyer_role clamps to 3 and organizations/person have no
  # cap of their own regardless of what's passed, so raising this only
  # actually changes concurrency for the note entity.
  [ValidateRange(1, 16)]
  [int]$Workers = 4,
  [string]$DevDealOwnerWorkspaceMemberId,
  [switch]$DeleteOrphaned,
  [switch]$MigrateMandates,
  [switch]$Apply,
  # A -Apply run of this script writes many records to DEV Attio in quick
  # succession, each one independently firing the real-time Attio-to-Postgres
  # webhook (workflows/wusool-toolkit's POST /webhooks/attio) -- correct, but
  # wasteful: buyer_role/seller_role entries in particular re-run their full
  # is_active sibling reconciliation on every single event. Paused for the
  # duration of the run by default, resumed automatically after (even on
  # failure -- see the try/finally below); -SkipWebhookPause opts out, e.g.
  # if the webhook isn't registered yet in this environment.
  [switch]$SkipWebhookPause
)

# Single entry point for the source-to-source migration: reads the
# workspace's own native Companies/People/Deals/buyer_brain/valuation_tool_leads
# and writes into the NEW custom objects/lists built for this migration
# (organizations/person/deal/buyer_role/seller_role) -- all in the SAME
# workspace, via the same SOURCE_ATTIO_API_KEY for both read and write, and
# never touching the native objects' own data. This is the source-attio
# counterpart of dev-attio/sync-all.ps1 (which instead writes to a separate
# DEV workspace and needs a SOURCE->DEV workspace-member crosswalk); that
# crosswalk does not apply here since every actor reference is already a
# valid member of this one workspace.
#
# Wraps the existing, already-tested sync-objects.ps1 / sync-lists.ps1
# rather than reimplementing their sync logic -- composition over rewrite,
# since those scripts already encode a lot of hard-won, tested behavior per
# entity.
#
# Fixed dependency order (proven in practice, not just theoretical):
#   organizations -> person -> buyer_role -> seller_role -> deal -> note
# Organizations must come first: Deal/Buyer Role/Seller Role are all
# parented to Organization, and Deal sync throws if a SOURCE company isn't
# in the new Organizations object yet. Person before Buyer Role: key_contact
# resolution needs the new Person records. Buyer Role/Seller Role before
# Deal so both are already populated by the time Deal sync runs. Note runs
# last of all -- it links back to whichever of organizations/person/
# buyer_role/seller_role a note is about, via workflows/crm-sync/scripts/
# source-attio/backfill-notes.ps1, so all of those need to already exist.
#
# -Entities lets you run the full pipeline or just a subset, always in the
# order above regardless of how you list them. Fails fast: the first
# entity that fails stops the whole run, nothing after it is attempted.

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($SourceApiKey)) {
  $SourceApiKey = [Environment]::GetEnvironmentVariable("SOURCE_ATTIO_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($DevApiKey)) {
  $DevApiKey = [Environment]::GetEnvironmentVariable("SOURCE_ATTIO_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($SourceApiKey)) { throw "Missing SOURCE_ATTIO_API_KEY." }
if ([string]::IsNullOrWhiteSpace($DevApiKey)) { throw "Missing SOURCE_ATTIO_API_KEY." }
if ($DeleteOrphaned -and ($Entities.Count -ne 1 -or $Entities[0] -ne "deal")) {
  throw "-DeleteOrphaned only supports -Entities deal."
}
if ($MigrateMandates -and ($Entities.Count -ne 1 -or $Entities[0] -ne "deal")) {
  throw "-MigrateMandates only supports -Entities deal."
}

$devHeaders = @{
  Authorization  = "Bearer $($DevApiKey.Trim())"
  Accept         = "application/json"
  "Content-Type" = "application/json"
}

function Invoke-AttioRequest {
  param(
    [ValidateSet("Get", "Patch")]
    [string]$Method,
    [string]$Path,
    [object]$Body
  )
  for ($attempt = 1; $attempt -le 8; $attempt++) {
    try {
      $parameters = @{ Method = $Method; Uri = "https://api.attio.com/v2$Path"; Headers = $devHeaders }
      if ($null -ne $Body) {
        $parameters.Body = [System.Text.Encoding]::UTF8.GetBytes(($Body | ConvertTo-Json -Depth 20))
      }
      return Invoke-RestMethod @parameters
    } catch {
      $statusCode = 0
      if ($_.Exception.Response) { $statusCode = [int]$_.Exception.Response.StatusCode }
      if ($attempt -eq 8 -or ($statusCode -ne 429 -and $statusCode -lt 500)) { throw }
      $delay = [Math]::Min(60, 5 * $attempt)
      Write-Warning "Attio $Method $Path returned HTTP $statusCode. Retrying in $delay seconds."
      Start-Sleep -Seconds $delay
    }
  }
}

# Finds the one webhook this system registered (see the webhook-registration
# runbook handed over separately) so its subscriptions can be paused/resumed
# around a bulk -Apply run. Deliberately does not assume a single webhook
# always exists (a fresh environment may not have registered one yet) or
# guess which one is "ours" if more than one is present -- either case just
# skips the pause with a warning rather than risk pausing/breaking the wrong
# webhook.
function Get-DevWebhook {
  $response = Invoke-AttioRequest -Method Get -Path "/webhooks"
  $webhooks = @($response.data)
  if ($webhooks.Count -eq 0) {
    Write-Warning "No Attio webhook is registered in this workspace -- nothing to pause. Continuing without pausing."
    return $null
  }
  if ($webhooks.Count -gt 1) {
    Write-Warning "$($webhooks.Count) Attio webhooks are registered -- ambiguous which one is the DEV-to-Postgres sync. Continuing without pausing."
    return $null
  }
  return $webhooks[0]
}

$canonicalOrder = @("organizations", "person", "buyer_role", "seller_role", "deal", "note")
$orderedEntities = @($canonicalOrder | Where-Object { $Entities -contains $_ })
$objectEntities = @("organizations", "person", "deal")

$listConfirmations = @{
  buyer_role  = @{ bounded = "APPLY_BUYER_ROLE_TO_DEV"; full = "APPLY_ALL_BUYER_ROLE_TO_DEV" }
  seller_role = @{ bounded = "APPLY_SELLER_ROLE_TO_DEV"; full = "APPLY_ALL_SELLER_ROLE_TO_DEV" }
}

# Parallel apply is only actually implemented, today, for organizations,
# person (via sync-objects.ps1 -Parallel), buyer_role (via
# sync-lists.ps1 -Workers chunked apply), and note (via backfill-notes.ps1's
# own -Workers runspace pool). seller_role and deals always run
# single-threaded regardless of -Parallel -- flagged below rather than
# silently pretending they're parallel.
$parallelCapable = @("organizations", "person", "buyer_role", "note")

Write-Host "Migration order for this run: $($orderedEntities -join ' -> ')"
Write-Host "Mode: $(if ($Apply) { 'APPLY' } else { 'DRY RUN' })"
if ($Parallel) {
  $notParallelCapable = @($orderedEntities | Where-Object { $parallelCapable -notcontains $_ })
  if ($notParallelCapable.Count -gt 0) {
    Write-Host "Note: -Parallel has no effect on $($notParallelCapable -join ', ') -- those always run single-threaded."
  }
}
Write-Host ""

# Paused before the migration writes anything, resumed in the `finally`
# below no matter how the run ends (success, a caught entity failure, or a
# terminating error) -- a migration that fails must never leave the
# real-time sync silently paused. Dry runs write nothing to DEV Attio, so
# nothing would fire the webhook anyway; only -Apply pauses it.
#
# Entirely best-effort, wrapped in its own try/catch: this is a safety net
# ON TOP OF the migration, and a problem with it (missing API key scope, a
# transient Attio error, anything) must never abort the migration itself --
# that would be strictly worse than the wasted-reconciliation-churn problem
# it exists to prevent. Any failure here just warns and proceeds unpaused.
$devWebhook = $null
$webhookPaused = $false
if ($Apply -and -not $SkipWebhookPause) {
  try {
    $devWebhook = Get-DevWebhook
    if ($null -ne $devWebhook) {
      Write-Host "Pausing Attio webhook $($devWebhook.id.webhook_id) for the duration of this run..."
      Invoke-AttioRequest -Method Patch -Path "/webhooks/$($devWebhook.id.webhook_id)" -Body @{
        data = @{ target_url = $devWebhook.target_url; subscriptions = @() }
      } | Out-Null
      $webhookPaused = $true
    }
  } catch {
    Write-Warning "Could not pause the Attio webhook ($($_.Exception.Message)) -- continuing without pausing."
    $devWebhook = $null
    $webhookPaused = $false
  }
}

try {
  foreach ($entity in $orderedEntities) {
    Write-Host ""
    Write-Host "===== $entity ====="

    $exitedCleanly = $true
    try {
      if ($objectEntities -contains $entity) {
        $objArgs = @{
          Objects      = @($entity)
          SourceApiKey = $SourceApiKey
          DevApiKey    = $DevApiKey
          Limit        = $Limit
        }
        if ($entity -ne "deal" -and $Parallel -and $Limit -eq 0) {
          $objArgs.Parallel = $true
          # sync-objects.ps1 has its own hard ValidateRange(1,8) on -Workers
          # (separate from this script's, which goes up to 16 to accommodate
          # note's own 16-worker ceiling) -- clamp here so a higher -Workers
          # value doesn't fail organizations/person outright.
          $objArgs.Workers = [Math]::Min($Workers, 8)
        }
        if ($entity -eq "deal" -and -not [string]::IsNullOrWhiteSpace($DevDealOwnerWorkspaceMemberId)) {
          $objArgs.DevDealOwnerWorkspaceMemberId = $DevDealOwnerWorkspaceMemberId
        }
        if ($entity -eq "deal" -and $DeleteOrphaned) {
          $objArgs.DeleteOrphaned = $true
          if ($Apply) { $objArgs.Apply = $true; $objArgs.Confirmation = "DELETE_ORPHANED_DEALS_FROM_DEV" }
        } elseif ($Apply) {
          $objArgs.Apply = $true
          $objArgs.Confirmation = "APPLY_SELECTED_OBJECTS_TO_DEV"
        }
        if ($entity -eq "deal" -and $MigrateMandates) { $objArgs.MigrateMandates = $true }
        & (Join-Path $PSScriptRoot "sync-objects.ps1") @objArgs
        $exitedCleanly = $?
      } elseif ($entity -eq "note") {
        # backfill-notes.ps1 is its own script, not sync-objects.ps1/
        # sync-lists.ps1 -- it has no SOURCE counterpart to migrate from (it
        # reads native Notes + the buyer_role list directly, both already in
        # this same workspace), so it takes a different, simpler parameter
        # shape (single API key, no -DevApiKey). Covers both note_type=Manual
        # and note_type=Meeting from Attio alone (Meeting is auto-detected by
        # content, e.g. a Granola transcript link) -- no Postgres involved,
        # same as every other entity in this pipeline.
        $noteArgs = @{
          SourceApiKey = $SourceApiKey
          Limit        = $Limit
        }
        if ($Parallel) { $noteArgs.Workers = [Math]::Min([Math]::Max($Workers, 1), 16) }
        if ($Apply) {
          $noteArgs.Apply = $true
          $noteArgs.Confirmation = "APPLY_NOTES_BACKFILL_TO_SOURCE"
        }
        & (Join-Path $PSScriptRoot "backfill-notes.ps1") @noteArgs
        $exitedCleanly = $?
      } else {
        $listArgs = @{
          Lists        = @($entity)
          SourceApiKey = $SourceApiKey
          DevApiKey    = $DevApiKey
          Limit        = $Limit
        }
        if ($entity -eq "buyer_role" -and $Parallel) { $listArgs.Workers = [Math]::Min($Workers, 3) }
        if ($Apply) {
          $listArgs.Apply = $true
          $listArgs.Confirmation = if ($Limit -eq 0) { $listConfirmations[$entity].full } else { $listConfirmations[$entity].bounded }
        }
        & (Join-Path $PSScriptRoot "sync-lists.ps1") @listArgs
        $exitedCleanly = $?
      }
    } catch {
      Write-Host ""
      Write-Host "FAILED at '$entity': $($_.Exception.Message)"
      Write-Host "Stopping -- no further entities will be processed."
      throw
    }

    if (-not $exitedCleanly) {
      Write-Host ""
      Write-Host "FAILED at '$entity' (non-terminating error)."
      Write-Host "Stopping -- no further entities will be processed."
      throw "$entity sync did not complete cleanly."
    }
  }

  Write-Host ""
  Write-Host "All requested entities completed successfully: $($orderedEntities -join ', ')"
} finally {
  # try/catch here too, but for the opposite reason as the pause block above:
  # a `finally` that throws replaces whatever exception or success was
  # already propagating, silently swallowing the real migration result. A
  # failed resume is a genuine problem (the webhook is left paused until
  # someone fixes it) -- it must be a loud, visible warning, never allowed
  # to clobber or mask the migration's own outcome.
  if ($webhookPaused) {
    try {
      Write-Host ""
      Write-Host "Resuming Attio webhook $($devWebhook.id.webhook_id)..."
      Invoke-AttioRequest -Method Patch -Path "/webhooks/$($devWebhook.id.webhook_id)" -Body @{
        data = @{ target_url = $devWebhook.target_url; subscriptions = $devWebhook.subscriptions }
      } | Out-Null
    } catch {
      Write-Warning "FAILED to resume Attio webhook $($devWebhook.id.webhook_id): $($_.Exception.Message)"
      Write-Warning "The webhook is still paused -- resume it manually (see the pause/resume runbook) before relying on real-time sync again."
    }
  }
}
