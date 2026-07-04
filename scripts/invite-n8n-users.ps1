param(
  [ValidateSet("dev", "prod")]
  [string] $Environment = "",

  [string] $BaseUrl = "",

  [string[]] $Email = @(),

  [string] $EmailFile = "",

  [string] $InviteEndpoint = "/rest/invitations",

  [string] $Cookie = $env:N8N_AUTH_COOKIE,

  [string] $ApiKey = $env:N8N_API_KEY,

  [switch] $DryRun
)

$ErrorActionPreference = "Stop"

$environmentUrls = @{
  dev  = "https://n8n-dev.wusoolcapital.com/"
  prod = "https://n8n-prod.wusoolcapital.com/"
}

function Join-Url {
  param(
    [string] $Root,
    [string] $Path
  )

  return $Root.TrimEnd("/") + "/" + $Path.TrimStart("/")
}

function Get-InvitePayload {
  param([string] $Address)

  return @{
    email = $Address
  } | ConvertTo-Json -Depth 5
}

if ([string]::IsNullOrWhiteSpace($BaseUrl)) {
  if ([string]::IsNullOrWhiteSpace($Environment)) {
    throw "Provide -Environment dev|prod or -BaseUrl."
  }

  $BaseUrl = $environmentUrls[$Environment]
}

if ([string]::IsNullOrWhiteSpace($BaseUrl)) {
  throw "Base URL could not be resolved."
}

$emails = New-Object System.Collections.Generic.List[string]

foreach ($address in $Email) {
  if (-not [string]::IsNullOrWhiteSpace($address)) {
    $emails.Add($address.Trim())
  }
}

if (-not [string]::IsNullOrWhiteSpace($EmailFile)) {
  if (-not (Test-Path -LiteralPath $EmailFile)) {
    throw "Email file not found: $EmailFile"
  }

  Get-Content -LiteralPath $EmailFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -ne "" -and -not $line.StartsWith("#")) {
      $emails.Add($line)
    }
  }
}

$uniqueEmails = $emails | Sort-Object -Unique

if ($uniqueEmails.Count -eq 0) {
  throw "Provide at least one email using -Email or -EmailFile."
}

$inviteUrl = Join-Url -Root $BaseUrl -Path $InviteEndpoint
Write-Host "n8n invite endpoint: $inviteUrl"
if (-not [string]::IsNullOrWhiteSpace($Environment)) {
  Write-Host "Environment: $Environment"
}

if ($DryRun) {
  foreach ($address in $uniqueEmails) {
    Write-Host "[DRY RUN] Would invite: $address"
  }
  exit 0
}

if ([string]::IsNullOrWhiteSpace($Cookie) -and [string]::IsNullOrWhiteSpace($ApiKey)) {
  throw "Set N8N_AUTH_COOKIE or N8N_API_KEY before running without -DryRun."
}

$headers = @{
  "Content-Type" = "application/json"
}

if (-not [string]::IsNullOrWhiteSpace($Cookie)) {
  $headers["Cookie"] = $Cookie
}

if (-not [string]::IsNullOrWhiteSpace($ApiKey)) {
  $headers["X-N8N-API-KEY"] = $ApiKey
}

foreach ($address in $uniqueEmails) {
  $payload = Get-InvitePayload -Address $address
  Write-Host "Inviting $address ..."

  try {
    Invoke-RestMethod `
      -Method Post `
      -Uri $inviteUrl `
      -Headers $headers `
      -Body $payload | Out-Null

    Write-Host "Invited $address"
  }
  catch {
    $details = $_.Exception.Message

    if ($_.Exception.Response -and $_.Exception.Response.GetResponseStream()) {
      $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
      $responseBody = $reader.ReadToEnd()

      if (-not [string]::IsNullOrWhiteSpace($responseBody)) {
        $details = "$details Response body: $responseBody"
      }
    }

    Write-Error "Failed to invite $address. $details"
  }
}
