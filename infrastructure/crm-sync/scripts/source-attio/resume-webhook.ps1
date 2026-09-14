<#
Restores the Attio -> Postgres webhook's event subscriptions after a sync run
was killed before its `finally` could resume it.

sync-all-within-source.ps1 pauses the webhook by PATCHing subscriptions to an
empty list and restores the captured list on exit. A run killed mid-flight
never reaches that restore, and before the stash existed the captured list
died with the process -- leaving the webhook "active" in the Attio UI but
subscribed to nothing, so it silently delivered no events at all.

This reads the stash sync-all-within-source.ps1 writes before pausing and
PATCHes those subscriptions back. Dry-run by default; -Apply performs the write.

  .\resume-webhook.ps1           # show what would be restored
  .\resume-webhook.ps1 -Apply    # restore it
#>
param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [string]$StashPath,
  [switch]$Apply
)
$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($SourceApiKey)) {
  $SourceApiKey = [Environment]::GetEnvironmentVariable("SOURCE_ATTIO_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($SourceApiKey)) { throw "Missing SOURCE_ATTIO_API_KEY." }
if (-not $StashPath) { $StashPath = Join-Path $PSScriptRoot "..\..\..\..\outputs\attio-webhook-subscriptions.json" }
if (-not (Test-Path $StashPath)) {
  throw "No stash at $StashPath. Nothing to restore from -- re-add the events in Attio (Workspace settings -> Webhooks -> Events), then future runs will stash them automatically."
}

$headers = @{ Authorization = "Bearer $($SourceApiKey.Trim())"; Accept = "application/json" }
$stash = Get-Content $StashPath -Raw | ConvertFrom-Json
$subs = @($stash.subscriptions)
if ($subs.Count -eq 0) { throw "Stash at $StashPath holds 0 subscriptions -- refusing to restore an empty list." }

$live = (Invoke-RestMethod -Method Get -Uri "https://api.attio.com/v2/webhooks" -Headers $headers).data
$target = @($live | Where-Object { $_.id.webhook_id -eq $stash.webhook_id })
if ($target.Count -ne 1) { throw "Webhook $($stash.webhook_id) from the stash is not registered in this workspace." }
$current = @($target[0].subscriptions)

Write-Host "Webhook      : $($stash.webhook_id)"
Write-Host "Target URL   : $($target[0].target_url)"
Write-Host "Stashed at   : $($stash.captured_at)"
Write-Host "Live now     : $($current.Count) subscription(s)"
Write-Host "Stash holds  : $($subs.Count) subscription(s)"
foreach ($s in $subs) { Write-Host "   - $($s.event_type)" }

if ($current.Count -gt 0) {
  Write-Warning "The webhook already has $($current.Count) subscription(s) -- it is not paused. Restoring would overwrite the live list."
  if (-not $Apply) { Write-Host "`nDry run: nothing written."; return }
}
if (-not $Apply) { Write-Host "`nDry run complete. Re-run with -Apply to restore."; return }

$body = @{ data = @{ target_url = $stash.target_url; subscriptions = $subs } } | ConvertTo-Json -Depth 8
Invoke-RestMethod -Method Patch -Uri "https://api.attio.com/v2/webhooks/$($stash.webhook_id)" `
  -Headers $headers -ContentType "application/json" -Body $body | Out-Null
$after = @((Invoke-RestMethod -Method Get -Uri "https://api.attio.com/v2/webhooks" -Headers $headers).data |
  Where-Object { $_.id.webhook_id -eq $stash.webhook_id }).subscriptions
Write-Host "`nRestored. Webhook now has $(@($after).Count) subscription(s)."
