param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [string]$DatabaseUrl = $env:DATABASE_URL,
  [switch]$Apply
)

# Single entry point for SOURCE Attio -> prod PostgreSQL, up through notes.
# Wraps sync-source-to-prod.ps1 (organizations -> person -> deals -> buyer
# roles -> seller roles) then sync-notes-from-source.ps1, in that order --
# notes must run last since it resolves against everything the first script
# creates (organization_id/person_id/buyer_role_id/seller_role_id). Fails
# fast: if the first script fails, notes is never attempted.
#
# Same composition-over-rewrite idea as
# workflows/crm-sync/scripts/source-attio/sync-all-within-source.ps1, one
# level up the pipeline (that script produces the SOURCE custom objects this
# one reads).
#
# Meetings (sync-meetings-from-source.ps1) and the one-off activities
# backfill are deliberately NOT part of this wrapper -- separate, run
# on their own schedule.

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($SourceApiKey)) { throw "Missing SOURCE_ATTIO_API_KEY." }
if ($Apply -and [string]::IsNullOrWhiteSpace($DatabaseUrl)) { throw "Missing DATABASE_URL." }

$commonArgs = @{ SourceApiKey = $SourceApiKey; DatabaseUrl = $DatabaseUrl }
if ($Apply) { $commonArgs.Apply = $true }

Write-Host ""
Write-Host "===== 1/2: organizations -> person -> deals -> buyer roles -> seller roles ====="
& (Join-Path $PSScriptRoot "sync-source-to-prod.ps1") @commonArgs
if (-not $?) { throw "sync-source-to-prod.ps1 failed -- stopping before notes." }

Write-Host ""
Write-Host "===== 2/2: notes ====="
& (Join-Path $PSScriptRoot "sync-notes-from-source.ps1") @commonArgs
if (-not $?) { throw "sync-notes-from-source.ps1 failed." }

Write-Host ""
if ($Apply) { Write-Host "Full prod sync (through notes) applied successfully." }
else { Write-Host "Full prod sync (through notes) dry run complete. Re-run with -Apply to write." }
