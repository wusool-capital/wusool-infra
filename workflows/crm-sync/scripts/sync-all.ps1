param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [string]$DevApiKey = $env:DEV_ATTIO_API_KEY,
  [ValidateSet("organizations", "person", "buyer_role", "seller_role", "deals")]
  [string[]]$Entities = @("organizations", "person", "buyer_role", "seller_role", "deals"),
  [int]$Limit = 0,
  [switch]$Parallel,
  [ValidateRange(1, 8)]
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

# Single entry point for the whole DEV Attio migration. Wraps the existing,
# already-tested sync-objects.ps1 / sync-lists.ps1 rather than reimplementing
# their sync logic -- composition over rewrite, since those scripts already
# encode a lot of hard-won, tested behavior per entity.
#
# Fixed dependency order (proven in practice, not just theoretical):
#   organizations -> person -> buyer_role -> seller_role -> deals
# Organizations must come first: Deals/Buyer Role/Seller Role are all
# parented to Organization, and Deal sync throws if a SOURCE company isn't
# in DEV Organizations yet. Person before Buyer Role: key_contact resolution
# needs DEV Person records. Buyer Role/Seller Role before Deals so the Deal
# sync's Seller-Role self-heal fallback rarely has to fire.
#
# Mandates retired 2026-08-23: no longer an ensure-schema-managed object/list
# and not part of the entity pipeline above -- but the Mandates list itself
# still exists in DEV Attio, and -MigrateMandates (only valid with
# -Entities deals) can still one-time migrate any entry there into its own
# Deal record (deal_type set directly). Re-run it if a new Mandate entry
# ever shows up. See migration-decisions.json.
#
# -Entities lets you run the full pipeline or just a subset, always in the
# order above regardless of how you list them. Fails fast: the first
# entity that fails stops the whole run, nothing after it is attempted.

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($SourceApiKey)) {
  $SourceApiKey = [Environment]::GetEnvironmentVariable("SOURCE_ATTIO_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($DevApiKey)) {
  $DevApiKey = [Environment]::GetEnvironmentVariable("DEV_ATTIO_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($SourceApiKey)) { throw "Missing SOURCE_ATTIO_API_KEY." }
if ([string]::IsNullOrWhiteSpace($DevApiKey)) { throw "Missing DEV_ATTIO_API_KEY." }
if ($DeleteOrphaned -and ($Entities.Count -ne 1 -or $Entities[0] -ne "deals")) {
  throw "-DeleteOrphaned only supports -Entities deals."
}
if ($MigrateMandates -and ($Entities.Count -ne 1 -or $Entities[0] -ne "deals")) {
  throw "-MigrateMandates only supports -Entities deals."
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

$canonicalOrder = @("organizations", "person", "buyer_role", "seller_role", "deals")
$orderedEntities = @($canonicalOrder | Where-Object { $Entities -contains $_ })
$objectEntities = @("organizations", "person", "deals")

$listConfirmations = @{
  buyer_role  = @{ bounded = "APPLY_BUYER_ROLE_TO_DEV"; full = "APPLY_ALL_BUYER_ROLE_TO_DEV" }
  seller_role = @{ bounded = "APPLY_SELLER_ROLE_TO_DEV"; full = "APPLY_ALL_SELLER_ROLE_TO_DEV" }
}

# Parallel apply is only actually implemented, today, for organizations,
# person (via sync-objects.ps1 -Parallel) and buyer_role (via
# sync-lists.ps1 -Workers chunked apply). seller_role and deals always run
# single-threaded regardless of -Parallel -- flagged below rather than
# silently pretending they're parallel.
$parallelCapable = @("organizations", "person", "buyer_role")

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
        if ($entity -ne "deals" -and $Parallel -and $Limit -eq 0) {
          $objArgs.Parallel = $true
          $objArgs.Workers = $Workers
        }
        if ($entity -eq "deals" -and -not [string]::IsNullOrWhiteSpace($DevDealOwnerWorkspaceMemberId)) {
          $objArgs.DevDealOwnerWorkspaceMemberId = $DevDealOwnerWorkspaceMemberId
        }
        if ($entity -eq "deals" -and $DeleteOrphaned) {
          $objArgs.DeleteOrphaned = $true
          if ($Apply) { $objArgs.Apply = $true; $objArgs.Confirmation = "DELETE_ORPHANED_DEALS_FROM_DEV" }
        } elseif ($Apply) {
          $objArgs.Apply = $true
          $objArgs.Confirmation = "APPLY_SELECTED_OBJECTS_TO_DEV"
        }
        if ($entity -eq "deals" -and $MigrateMandates) { $objArgs.MigrateMandates = $true }
        & (Join-Path $PSScriptRoot "sync-objects.ps1") @objArgs
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
