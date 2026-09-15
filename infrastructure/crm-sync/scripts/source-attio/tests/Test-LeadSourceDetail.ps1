# Assertions for `Get-LatestLeadSourceDetail` in ../_internal/objects.ps1, which
# collapses SOURCE's multiselect `companies.lead_source` down to the single
# value the target `lead_source_detail` can hold.
#
# Run by hand: pwsh -File ./tests/Test-LeadSourceDetail.ps1
#
# Not wired into CI: there is no PowerShell test runner in this repo yet
# (`checks.sh shell` runs one bash file, `powershell-quality` runs only
# PSScriptAnalyzer). It is kept because the function has three separate throw
# paths and a timestamp sort, and the Arto case below is real production data.
#
# The functions under test are extracted from the shipped script rather than
# reimplemented, so these assertions cannot drift from what actually runs.

$ErrorActionPreference = "Stop"

$src = Join-Path $PSScriptRoot "..\_internal\objects.ps1"
$text = Get-Content $src -Raw
foreach ($name in @("Get-ScalarValue", "Get-LatestLeadSourceDetail")) {
  $match = [regex]::Match($text, "(?ms)^function $name \{.*?^\}")
  if (-not $match.Success) { throw "could not extract $name from $src" }
  Invoke-Expression $match.Value
}

$script:failures = 0

function Assert-Value {
  param([string]$Label, $Expected, $Actual)
  if ($Expected -eq $Actual) {
    Write-Output "  PASS  $Label -> '$Actual'"
  } else {
    Write-Output "  FAIL  ${Label}: expected '$Expected', got '$Actual'"
    $script:failures++
  }
}

function Assert-Throws {
  param([string]$Label, [scriptblock]$Block)
  try {
    & $Block
    Write-Output "  FAIL  ${Label}: expected a throw, got none"
    $script:failures++
  } catch {
    Write-Output "  PASS  $Label refused: $($_.Exception.Message)"
  }
}

function New-Values { param($Items) [pscustomobject]@{ lead_source = $Items } }
function New-Option {
  param([string]$Title, $ActiveFrom, $ActiveUntil = $null)
  [pscustomobject]@{
    option       = [pscustomobject]@{ title = $Title }
    active_from  = $ActiveFrom
    active_until = $ActiveUntil
  }
}

Write-Output "an organization with no lead_source at all"
Assert-Value "unset" $null (Get-LatestLeadSourceDetail -Values (New-Values @()))

Write-Output "a single value passes straight through"
Assert-Value "one tool" "Valuation Tool" (Get-LatestLeadSourceDetail -Values (New-Values @(
  New-Option "Valuation Tool" "2026-04-09T08:56:17.009000000Z")))

Write-Output "two tools: the most recent active_from wins (Arto, real data)"
Assert-Value "Arto" "M&A Readiness Tool" (Get-LatestLeadSourceDetail -Values (New-Values @(
  New-Option "Valuation Tool"     "2026-04-09T08:56:17.009000000Z"
  New-Option "M&A Readiness Tool" "2026-04-09T09:12:27.347000000Z")))

Write-Output "array order must not change the answer"
Assert-Value "Arto reversed" "M&A Readiness Tool" (Get-LatestLeadSourceDetail -Values (New-Values @(
  New-Option "M&A Readiness Tool" "2026-04-09T09:12:27.347000000Z"
  New-Option "Valuation Tool"     "2026-04-09T08:56:17.009000000Z")))

Write-Output "a superseded value cannot win, even though it is newer"
Assert-Value "retired value skipped" "Valuation Tool" (Get-LatestLeadSourceDetail -Values (New-Values @(
  New-Option "Valuation Tool"     "2026-04-09T08:56:17.009000000Z"
  New-Option "M&A Readiness Tool" "2026-04-09T09:12:27.347000000Z" "2026-05-01T00:00:00Z")))

Write-Output "the same title twice needs no timestamps to disambiguate"
Assert-Value "duplicate title" "Buyer Form" (Get-LatestLeadSourceDetail -Values (New-Values @(
  New-Option "Buyer Form" $null
  New-Option "Buyer Form" $null)))

Write-Output "genuine ambiguity is refused, never guessed"
Assert-Throws "missing active_from on a conflict" {
  Get-LatestLeadSourceDetail -Values (New-Values @(
    New-Option "Valuation Tool" $null
    New-Option "Buyer Form"     "2026-04-09T09:12:27Z"))
}
Assert-Throws "tied active_from on different titles" {
  Get-LatestLeadSourceDetail -Values (New-Values @(
    New-Option "Valuation Tool" "2026-04-09T08:56:17Z"
    New-Option "Buyer Form"     "2026-04-09T08:56:17Z"))
}

Write-Output ""
if ($script:failures -gt 0) {
  Write-Output "FAILED: $script:failures assertion(s)"
  exit 1
}
Write-Output "all assertions passed"
exit 0
