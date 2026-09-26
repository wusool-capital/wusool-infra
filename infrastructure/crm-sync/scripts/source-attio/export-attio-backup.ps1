param(
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [ValidateSet("organizations", "person", "deal", "note", "buyer_role", "seller_role")]
  [string[]]$Entities = @("organizations", "person", "deal", "note", "buyer_role", "seller_role"),
  [string]$OutputRoot
)

# Captures the six mirrored Attio entities as raw JSON, so a migration can be
# rolled back by `restore-attio-backup.ps1`.
#
# Read-only: it issues query calls and writes files. There is no -Apply because
# there is nothing to apply. Run it before every migration step.
#
# Four of the six are objects and two are lists, which take different endpoints
# and return different shapes -- records have `id.record_id` and `values`,
# entries have `id.entry_id`, `parent_record_id` and `entry_values`. Both are
# stored verbatim; restore knows the difference.
#
# Captures both halves of the workspace, test and production alike. A backup
# that silently omitted the other half would restore into a state that never
# existed.
#
# Local only, and `outputs/` is gitignored -- this is one copy on one machine.

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($SourceApiKey)) {
  $SourceApiKey = [Environment]::GetEnvironmentVariable("SOURCE_ATTIO_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($SourceApiKey)) { throw "Missing SOURCE_ATTIO_API_KEY." }

# Which endpoint each entity answers on. `note` is the unified custom object,
# slug `note` -- Attio reserves `notes` for its own per-record panel.
$entityKinds = @{
  organizations = "object"
  person        = "object"
  deal          = "object"
  note          = "object"
  buyer_role    = "list"
  seller_role   = "list"
}

$headers = @{
  Authorization = "Bearer $($SourceApiKey.Trim())"
  Accept = "application/json"
  "Content-Type" = "application/json"
}

$runId = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
  $OutputRoot = Join-Path $PSScriptRoot "..\..\..\..\outputs\attio_migration\backups"
}
$backupDir = Join-Path $OutputRoot $runId
$null = New-Item -ItemType Directory -Force -Path $backupDir

function Write-Json {
  param([string]$Path, [object]$Value)
  [IO.File]::WriteAllText(
    $Path, ($Value | ConvertTo-Json -Depth 40), [Text.UTF8Encoding]::new($false)
  )
}

function Invoke-AttioRequest {
  param(
    [ValidateSet("Get", "Post")][string]$Method,
    [string]$Path,
    [object]$Body
  )
  $parameters = @{ Method = $Method; Uri = "https://api.attio.com/v2$Path"; Headers = $headers }
  if ($null -ne $Body) {
    $parameters.Body = [Text.Encoding]::UTF8.GetBytes(($Body | ConvertTo-Json -Depth 30))
  }
  for ($attempt = 1; ; $attempt++) {
    try { return Invoke-RestMethod @parameters }
    catch {
      $status = [int]$_.Exception.Response.StatusCode
      if ($attempt -ge 8 -or ($status -ne 429 -and $status -lt 500)) { throw }
      Start-Sleep -Seconds ([Math]::Min(5 * $attempt, 60))
    }
  }
}

function Get-PagedData {
  param([string]$Path)
  $all = @()
  for ($offset = 0; ; $offset += 500) {
    $response = Invoke-AttioRequest -Method Post -Path $Path -Body @{ limit = 500; offset = $offset }
    $page = @($response.data)
    $all += $page
    Write-Host ("  ...{0} captured" -f $all.Count)
    if ($page.Count -lt 500) { return $all }
  }
}

$decisions = Get-Content (Join-Path $PSScriptRoot "config\migration-decisions.json") -Raw |
  ConvertFrom-Json
$expectedWorkspaceId = [string]$decisions.workspace_id
$organizationsObject = Invoke-AttioRequest -Method Get -Path "/objects/organizations"
$connectedWorkspaceId = [string]$organizationsObject.data.id.workspace_id
if ($connectedWorkspaceId -ne $expectedWorkspaceId) {
  throw "Workspace mismatch. Expected $expectedWorkspaceId but connected to $connectedWorkspaceId."
}

$counts = [ordered]@{}
foreach ($entity in $Entities) {
  $kind = $entityKinds[$entity]
  $path = if ($kind -eq "object") {
    "/objects/$entity/records/query"
  } else {
    "/lists/$entity/entries/query"
  }

  Write-Host "Capturing $entity ($kind)..."
  $rows = Get-PagedData -Path $path
  $counts[$entity] = $rows.Count

  Write-Json -Path (Join-Path $backupDir "$entity.json") -Value @{
    entity = $entity
    kind = $kind
    endpoint = $path
    captured_at_utc = [DateTime]::UtcNow.ToString("o")
    count = $rows.Count
    rows = $rows
  }
}

$manifest = [ordered]@{
  run_id = $runId
  captured_at_utc = [DateTime]::UtcNow.ToString("o")
  workspace_id = $connectedWorkspaceId
  entities = $counts
  # Restore reads this to know which endpoint each file came from.
  kinds = $entityKinds
}
Write-Json -Path (Join-Path $backupDir "manifest.json") -Value $manifest

$manifest | Format-List
Write-Host "Backup written to $backupDir"
