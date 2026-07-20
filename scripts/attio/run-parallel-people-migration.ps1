param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [string]$DevApiKey = $env:DEV_ATTIO_API_KEY,
  [int]$StartOffset = 0,
  [int]$MaxRecords = 4300,
  [int]$WorkerCount = 3,
  [int]$PageLimit = 250,
  [switch]$UseFallbackNames,
  [switch]$Apply
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($SourceApiKey)) {
  throw "Missing SOURCE_ATTIO_API_KEY."
}

if ([string]::IsNullOrWhiteSpace($DevApiKey)) {
  throw "Missing DEV_ATTIO_API_KEY."
}

if ($WorkerCount -lt 1) {
  throw "WorkerCount must be at least 1."
}

if ($MaxRecords -lt 1) {
  throw "MaxRecords must be at least 1."
}

$repoRoot = (Resolve-Path ".").Path
$scriptPath = Join-Path $repoRoot "scripts\attio\migrate-people-fast.ps1"
$chunkSize = [Math]::Ceiling($MaxRecords / $WorkerCount)
$jobs = @()

for ($worker = 0; $worker -lt $WorkerCount; $worker++) {
  $workerOffset = $StartOffset + ($worker * $chunkSize)
  $workerMaxRecords = [Math]::Min($chunkSize, ($StartOffset + $MaxRecords) - $workerOffset)

  if ($workerMaxRecords -le 0) {
    continue
  }

  Write-Host "Starting people worker $($worker + 1): offset=$workerOffset maxRecords=$workerMaxRecords"

  $jobs += Start-Job -Name "people-$workerOffset" -ScriptBlock {
    param(
      [string]$RepoRoot,
      [string]$ScriptPath,
      [string]$SourceApiKey,
      [string]$DevApiKey,
      [int]$WorkerOffset,
      [int]$WorkerMaxRecords,
      [int]$PageLimit,
      [bool]$UseFallbackNames,
      [bool]$Apply
    )

    Set-Location $RepoRoot
    $env:SOURCE_ATTIO_API_KEY = $SourceApiKey
    $env:DEV_ATTIO_API_KEY = $DevApiKey

    $args = @(
      "-ExecutionPolicy", "Bypass",
      "-File", $ScriptPath,
      "-StartOffset", $WorkerOffset,
      "-MaxRecords", $WorkerMaxRecords,
      "-Limit", $PageLimit
    )

    if ($UseFallbackNames) {
      $args += "-UseFallbackNames"
    }

    if ($Apply) {
      $args += "-Apply"
    }

    & powershell @args
  } -ArgumentList @(
    $repoRoot,
    $scriptPath,
    $SourceApiKey,
    $DevApiKey,
    $workerOffset,
    $workerMaxRecords,
    $PageLimit,
    [bool]$UseFallbackNames,
    [bool]$Apply
  )
}

while (($jobs | Where-Object { $_.State -eq "Running" }).Count -gt 0) {
  foreach ($job in $jobs) {
    Receive-Job -Job $job
  }

  Start-Sleep -Seconds 5
}

foreach ($job in $jobs) {
  Receive-Job -Job $job
}

$failedJobs = @($jobs | Where-Object { $_.State -ne "Completed" })
Remove-Job -Job $jobs

if ($failedJobs.Count -gt 0) {
  throw "$($failedJobs.Count) parallel people migration worker(s) failed."
}

Write-Host "Parallel people migration complete."
