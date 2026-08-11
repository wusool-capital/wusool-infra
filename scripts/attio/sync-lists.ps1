param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [string]$DevApiKey = $env:DEV_ATTIO_API_KEY,
  [ValidateSet("buyer_role", "seller_role", "mandates")]
  [string[]]$Lists = @("buyer_role", "seller_role", "mandates"),
  [int]$SampleSize = 10,
  [ValidateRange(1, 3)]
  [int]$Workers = 3,
  [int]$Limit = 0,
  [string]$Confirmation,
  [switch]$Apply
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($SourceApiKey)) {
  $SourceApiKey = [Environment]::GetEnvironmentVariable("SOURCE_ATTIO_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($DevApiKey)) {
  $DevApiKey = [Environment]::GetEnvironmentVariable("DEV_ATTIO_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($SourceApiKey)) { throw "Missing SOURCE_ATTIO_API_KEY." }
if ([string]::IsNullOrWhiteSpace($DevApiKey)) { throw "Missing DEV_ATTIO_API_KEY." }

$decisions = Get-Content (Join-Path $PSScriptRoot "config\migration-decisions.json") -Raw |
  ConvertFrom-Json
$expectedWorkspaceId = [string]$decisions.dev_workspace_id

function Invoke-AttioRequest {
  param(
    [ValidateSet("Get", "Post")][string]$Method,
    [hashtable]$Headers,
    [string]$Path,
    [object]$Body
  )
  $parameters = @{
    Method = $Method
    Uri = "https://api.attio.com/v2$Path"
    Headers = $Headers
  }
  if ($null -ne $Body) {
    $parameters.Body = [Text.Encoding]::UTF8.GetBytes(
      ($Body | ConvertTo-Json -Depth 30)
    )
  }
  Invoke-RestMethod @parameters
}

$devHeaders = @{
  Authorization = "Bearer $($DevApiKey.Trim())"
  Accept = "application/json"
  "Content-Type" = "application/json"
}
$devOrganization = Invoke-AttioRequest -Method Get -Headers $devHeaders `
  -Path "/objects/organizations"
$connectedWorkspaceId = [string]$devOrganization.data.id.workspace_id
if ($connectedWorkspaceId -ne $expectedWorkspaceId) {
  throw "DEV workspace mismatch. Expected $expectedWorkspaceId but connected to $connectedWorkspaceId."
}

$workerPaths = @{
  buyer_role = (Join-Path $PSScriptRoot "_internal\lists.ps1")
  seller_role = (Join-Path $PSScriptRoot "_internal\lists.ps1")
  mandates = (Join-Path $PSScriptRoot "_internal\lists.ps1")
}
$schemaChecks = @{
  buyer_role = "buyer_role"
  seller_role = "seller_role"
  mandates = "mandates"
}

$results = [System.Collections.Generic.List[object]]::new()
$readyLists = [System.Collections.Generic.List[string]]::new()

foreach ($list in $Lists) {
  Write-Host ""
  Write-Host "== Schema preflight: $list =="
  $schemaArgs=@{Entities=@($list);SourceApiKey=$SourceApiKey;DevApiKey=$DevApiKey}
  if($Apply){$schemaArgs.FailOnDrift=$true}
  & (Join-Path $PSScriptRoot "ensure-schema.ps1") @schemaArgs
  if (-not $?) { throw "$list schema preflight failed." }

  $worker = $workerPaths[$list]
  if (-not (Test-Path $worker)) {
    $results.Add([pscustomobject]@{
      list = $list
      status = "worker_pending"
      writes = 0
    })
    Write-Warning "$list worker is not implemented yet; no writes performed."
    continue
  }
  $readyLists.Add($list)
}

if ($Apply) {
  if ($Lists.Count -ne 1) {
    throw "Apply exactly one reviewed list at a time."
  }
  if ($Lists[0] -eq "seller_role") {
    $isBoundedSellerApply = $Limit -ge 1 -and $Limit -le 10 -and
      $Confirmation -eq "APPLY_SELLER_ROLE_TO_DEV"
    $isFullSellerApply = $Limit -eq 0 -and
      $Confirmation -eq "APPLY_ALL_SELLER_ROLE_TO_DEV"
    if (-not $isBoundedSellerApply -and -not $isFullSellerApply) {
      throw "Use a 1-10 limit with APPLY_SELLER_ROLE_TO_DEV, or Limit 0 with APPLY_ALL_SELLER_ROLE_TO_DEV."
    }
    $worker = $workerPaths["seller_role"]
    & powershell -NoProfile -ExecutionPolicy Bypass -File $worker `
      -Task seller_role -Apply -Limit $Limit -SampleSize $SampleSize -Confirmation $Confirmation
    if ($LASTEXITCODE -ne 0) { throw "Seller Role apply failed." }
    Write-Host "Unified Seller Role apply complete."
    return
  }
  if ($Lists[0] -eq "mandates") {
    $isBoundedMandatesApply = $Limit -ge 1 -and $Limit -le 10 -and
      $Confirmation -eq "APPLY_MANDATES_TO_DEV"
    $isFullMandatesApply = $Limit -eq 0 -and
      $Confirmation -eq "APPLY_ALL_MANDATES_TO_DEV"
    if (-not $isBoundedMandatesApply -and -not $isFullMandatesApply) {
      throw "Use a 1-10 limit with APPLY_MANDATES_TO_DEV, or Limit 0 with APPLY_ALL_MANDATES_TO_DEV."
    }
    $worker = $workerPaths["mandates"]
    & powershell -NoProfile -ExecutionPolicy Bypass -File $worker `
      -Task mandates -Apply -Limit $Limit -SampleSize $SampleSize -Confirmation $Confirmation
    if ($LASTEXITCODE -ne 0) { throw "Mandates apply failed." }
    Write-Host "Unified Mandates apply complete."
    return
  }
  if ($Lists[0] -ne "buyer_role") {
    throw "Apply is not enabled for $($Lists[0])."
  }
  $isBoundedApply = $Limit -ge 1 -and $Limit -le 10 -and
    $Confirmation -eq "APPLY_BUYER_ROLE_TO_DEV"
  $isFullApply = $Limit -eq 0 -and
    $Confirmation -eq "APPLY_ALL_BUYER_ROLE_TO_DEV"
  if (-not $isBoundedApply -and -not $isFullApply) {
    throw "Use a 1-10 limit with APPLY_BUYER_ROLE_TO_DEV, or Limit 0 with APPLY_ALL_BUYER_ROLE_TO_DEV."
  }
  $worker = $workerPaths["buyer_role"]
  if ($isBoundedApply -or $Workers -eq 1) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $worker `
      -Task buyer_role -Apply -Limit $Limit -SampleSize $SampleSize -Confirmation $Confirmation
    if ($LASTEXITCODE -ne 0) { throw "Buyer Role apply failed." }
    Write-Host "Unified Buyer Role apply complete."
    return
  }

  Write-Host "Refreshing canonical Buyer Role plan before parallel apply."
  & powershell -NoProfile -ExecutionPolicy Bypass -File $worker -Task buyer_role -SampleSize $SampleSize
  if ($LASTEXITCODE -ne 0) { throw "Buyer Role planning dry-run failed." }
  $planPath = Join-Path $PSScriptRoot "..\..\outputs\attio_migration\buyer-role-plan.json"
  $plan = Get-Content $planPath -Raw | ConvertFrom-Json
  $total = [int]$plan.summary.resolved_plans
  if ($total -lt 1 -or [int]$plan.summary.unresolved_parents -ne 0 -or
      [int]$plan.summary.scalar_conflicts -ne 0) {
    throw "Buyer Role canonical plan is not safe for parallel apply."
  }

  $workerCount = [Math]::Min($Workers, $total)
  $chunkSize = [int][Math]::Ceiling($total / [double]$workerCount)
  $jobs = @()
  for ($index = 0; $index -lt $workerCount; $index++) {
    $start = $index * $chunkSize
    $count = [Math]::Min($chunkSize, $total - $start)
    if ($count -le 0) { continue }
    Write-Host "START APPLY WORKER $($index + 1): canonical offset=$start count=$count"
    $job = Start-Job -Name "buyer-role-apply-$($index + 1)" `
      -ArgumentList $worker,$start,$count,($index + 1),$SampleSize -ScriptBlock {
        param($WorkerPath, $ChunkStart, $ChunkCount, $WorkerNumber, $RequestedSampleSize)
        & powershell -NoProfile -ExecutionPolicy Bypass -File $WorkerPath `
          -Task buyer_role -Apply -StartIndex $ChunkStart -Limit $ChunkCount `
          -SampleSize $RequestedSampleSize `
          -OutputSuffix "worker-$WorkerNumber" `
          -Confirmation APPLY_ALL_BUYER_ROLE_TO_DEV
        if ($LASTEXITCODE -ne 0) { throw "Worker exited with code $LASTEXITCODE." }
      }
    $jobs += $job
  }

  $jobs | Wait-Job | Out-Null
  $failed = @($jobs | Where-Object State -ne "Completed")
  foreach ($job in $jobs) { Receive-Job -Job $job }
  foreach ($job in $jobs) { Remove-Job -Job $job -Force }
  if ($failed.Count -gt 0) {
    throw "$($failed.Count) Buyer Role apply worker(s) failed."
  }
  Write-Host "Unified parallel Buyer Role apply complete across $($jobs.Count) workers."
  return
}

$queue = [System.Collections.Generic.Queue[string]]::new()
foreach ($list in $readyLists) { $queue.Enqueue($list) }
$running = @()

while ($queue.Count -gt 0 -or $running.Count -gt 0) {
  while ($queue.Count -gt 0 -and $running.Count -lt $Workers) {
    $list = $queue.Dequeue()
    $worker = $workerPaths[$list]
    Write-Host "START PARALLEL DRY RUN: $list"
    $job = Start-Job -Name "attio-$list" -ArgumentList $worker,$SampleSize,$list -ScriptBlock {
      param($WorkerPath, $RequestedSampleSize, $ListTask)
      & powershell -NoProfile -ExecutionPolicy Bypass -File $WorkerPath `
        -Task $ListTask -SampleSize $RequestedSampleSize
      if ($LASTEXITCODE -ne 0) { throw "Worker exited with code $LASTEXITCODE." }
    }
    $running += [pscustomobject]@{ List = $list; Job = $job }
  }

  $completed = @($running | Where-Object { $_.Job.State -in @("Completed", "Failed", "Stopped") })
  if ($completed.Count -eq 0) {
    Start-Sleep -Milliseconds 250
    continue
  }

  foreach ($item in $completed) {
    Receive-Job -Job $item.Job
    if ($item.Job.State -ne "Completed") {
      $state = $item.Job.State
      Remove-Job -Job $item.Job -Force
      throw "$($item.List) parallel dry-run ended in state $state."
    }
    Remove-Job -Job $item.Job
    $results.Add([pscustomobject]@{
      list = $item.List
      status = "parallel_dry_run_complete"
      writes = 0
    })
    $running = @($running | Where-Object { $_.Job.Id -ne $item.Job.Id })
  }
}

Write-Host ""
$results | Format-Table -AutoSize
Write-Host "Unified list dry-run complete. No Attio records were written."
