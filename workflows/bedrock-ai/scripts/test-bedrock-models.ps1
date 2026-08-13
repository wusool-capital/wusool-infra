param(
  [string]$Region = "eu-central-1",
  [string]$RoleName,
  [string]$Project = "wusool",
  [string]$Environment = "dev"
)

# Re-checks live Bedrock invoke access for the model(s) in $models below.
# Uses the model-agnostic Converse API so one code path covers any vendor
# -- no per-vendor request-body branching.
#
# claude-haiku-4-5 and qwen3-235b-a22b are already confirmed working
# (PROGRESS.md) and were dropped from the default list below to keep this
# script focused on claude-sonnet-4-6, which is the one still being
# worked on -- add them back to $models if you need to re-verify all
# three again.
#
# Deliberately does NOT set $ErrorActionPreference = "Stop" and does NOT
# redirect aws.exe's stderr: in PowerShell 5.1, redirecting a native
# command's stderr wraps each line as a terminating NativeCommandError
# under Stop, which swallows the real AWS error text instead of showing
# it. Pass/fail is read from $LASTEXITCODE; AWS's own error message
# prints straight to the console, unredirected.
#
# --messages is passed via a file:// path, not an inline string:
# PowerShell mangles/strips embedded double quotes when it re-quotes an
# argument for a native exe, so an inline JSON string like
# '{"role":"user",...}' arrives at aws.exe as {role:user,...}. Writing
# the JSON to disk and passing file://<path> sidesteps PowerShell's
# native-argument quoting entirely.

if ([string]::IsNullOrWhiteSpace($RoleName)) {
  $RoleName = "$Project-$Environment-n8n-ec2"
}

$models = @(
  # Bare on-demand ID "anthropic.claude-sonnet-4-6" was rejected with a
  # ValidationException -- this model requires a cross-region inference
  # profile, same as claude-haiku-4-5. Confirmed via `aws bedrock
  # list-inference-profiles` that the EU profile ID is
  # "eu.anthropic.claude-sonnet-4-6".
  [pscustomobject]@{ Name = "claude-sonnet-4-6"; InvokeId = "eu.anthropic.claude-sonnet-4-6" }
)

Write-Host "== Caller identity =="
aws sts get-caller-identity --output table
Write-Host ""

Write-Host "== IAM policy check: $RoleName =="
$policyName = "$Project-$Environment-bedrock-invoke"
$null = aws iam get-role-policy --role-name $RoleName --policy-name $policyName --output json
if ($LASTEXITCODE -eq 0) {
  Write-Host "OK   inline policy '$policyName' present on role '$RoleName'"
}
else {
  Write-Host "FAIL inline policy '$policyName' not found on role '$RoleName' (see AWS error above)"
}
Write-Host ""

Write-Host "== Model invoke checks (region: $Region) =="
$results = @()

$messagesJson = '[{"role":"user","content":[{"text":"Say OK."}]}]'

foreach ($m in $models) {
  Write-Host "-- $($m.Name) ($($m.InvokeId)) --"
  $tmpFile = New-TemporaryFile
  [System.IO.File]::WriteAllText($tmpFile.FullName, $messagesJson, [System.Text.UTF8Encoding]::new($false))
  $null = aws bedrock-runtime converse --region $Region --model-id $m.InvokeId --messages "file://$($tmpFile.FullName)" --output json
  $exitCode = $LASTEXITCODE
  Remove-Item $tmpFile.FullName -ErrorAction SilentlyContinue
  if ($exitCode -eq 0) {
    Write-Host "PASS $($m.Name)"
    $results += [pscustomobject]@{ Model = $m.Name; Status = "PASS" }
  }
  else {
    Write-Host "FAIL $($m.Name) (see AWS error above)"
    $results += [pscustomobject]@{ Model = $m.Name; Status = "FAIL" }
  }
  Write-Host ""
}

Write-Host "== Summary =="
$results | Format-Table -AutoSize
