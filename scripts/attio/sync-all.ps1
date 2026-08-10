param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [string]$DevApiKey = $env:DEV_ATTIO_API_KEY,
  [ValidateSet("organizations", "person", "buyer_role", "seller_role", "deals", "mandates")]
  [string[]]$Entities = @("organizations", "person", "buyer_role", "seller_role", "deals", "mandates"),
  [int]$Limit = 0,
  [switch]$Parallel,
  [ValidateRange(1, 8)]
  [int]$Workers = 4,
  [string]$DevDealOwnerWorkspaceMemberId,
  [switch]$Apply
)

# Single entry point for the whole DEV Attio migration. Wraps the existing,
# already-tested sync-objects.ps1 / sync-lists.ps1 rather than reimplementing
# their sync logic -- composition over rewrite, since those scripts already
# encode a lot of hard-won, tested behavior per entity.
#
# Fixed dependency order (proven in practice, not just theoretical):
#   organizations -> person -> buyer_role -> seller_role -> deals -> mandates
# Organizations must come first: Deals/Buyer Role/Seller Role/Mandates are
# all parented to Organization, and Deal sync throws if a SOURCE company
# isn't in DEV Organizations yet. Person before Buyer Role: key_contact
# resolution needs DEV Person records. Buyer Role/Seller Role before Deals
# so the Deal sync's Seller-Role self-heal fallback rarely has to fire.
# Mandates last: nothing in this list depends on it.
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

$canonicalOrder = @("organizations", "person", "buyer_role", "seller_role", "deals", "mandates")
$orderedEntities = @($canonicalOrder | Where-Object { $Entities -contains $_ })
$objectEntities = @("organizations", "person", "deals")

$listConfirmations = @{
  buyer_role  = @{ bounded = "APPLY_BUYER_ROLE_TO_DEV"; full = "APPLY_ALL_BUYER_ROLE_TO_DEV" }
  seller_role = @{ bounded = "APPLY_SELLER_ROLE_TO_DEV"; full = "APPLY_ALL_SELLER_ROLE_TO_DEV" }
  mandates    = @{ bounded = "APPLY_MANDATES_TO_DEV"; full = "APPLY_ALL_MANDATES_TO_DEV" }
}

# Parallel apply is only actually implemented, today, for organizations,
# person (via sync-objects.ps1 -Parallel) and buyer_role (via
# sync-lists.ps1 -Workers chunked apply). seller_role, deals, and mandates
# always run single-threaded regardless of -Parallel -- flagged below
# rather than silently pretending they're parallel.
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
      if ($Apply) {
        $objArgs.Apply = $true
        $objArgs.Confirmation = "APPLY_SELECTED_OBJECTS_TO_DEV"
      }
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
