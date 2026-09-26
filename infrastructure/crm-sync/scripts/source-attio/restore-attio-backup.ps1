param(
  [Parameter(Mandatory = $true)]
  [string]$BackupDir,
  [string]$SourceApiKey = $env:SOURCE_ATTIO_API_KEY,
  [ValidateSet("buyer_role", "seller_role")]
  [string[]]$Entities = @("buyer_role", "seller_role"),
  [switch]$DeleteCreatedSince,
  [string]$Confirmation,
  [switch]$Apply
)

# Rolls a migration back from an `export-attio-backup.ps1` capture.
#
# Deliberately narrow: it restores only the fields the migration scripts in this
# directory write, listed in $restorableFields below. A generic "put every value
# back" restore would have to reverse Attio's read shape into its write shape for
# every attribute type on six entities, and get it right under pressure, with a
# 400 or a silently wrong value as the failure mode. Everything else in the
# backup file is evidence, not restore input.
#
# Two phases, both opt-in:
#   PATCH  -- every record still present gets its backed-up values written back.
#   DELETE -- records that exist now but not in the backup, i.e. created since
#             the capture. Requires -DeleteCreatedSince on top of -Apply. This is
#             the only destructive operation in this toolchain.
#
# What it cannot do: bring back a record deleted since the capture. Attio mints
# ids on create, so recreating one would give it a new id and silently break
# every foreign key pointing at the old one -- `match_results.buyer_role_id` is
# NOT NULL and cascades. Those are reported and left alone.
#
# Read-only fields (`created_at`, `created_by`, ids) are not restored.
#
# Writes to Attio only. The nightly mirror carries it into Postgres, same as
# every other script here -- never the reverse.

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($SourceApiKey)) {
  $SourceApiKey = [Environment]::GetEnvironmentVariable("SOURCE_ATTIO_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($SourceApiKey)) { throw "Missing SOURCE_ATTIO_API_KEY." }
if (-not (Test-Path $BackupDir)) { throw "Backup directory not found: $BackupDir" }

if ($Apply -and $Confirmation -ne "RESTORE_ATTIO_FROM_BACKUP") {
  throw "Pass -Apply -Confirmation RESTORE_ATTIO_FROM_BACKUP to write."
}

# Only what the migration scripts write, by write shape.
$restorableFields = @{
  buyer_role = @{
    select = @("target_vertical", "target_region", "target_country", "target_geography")
    text = @("geographic_focus", "target_stage", "ticket_size", "legacy_entry_id")
    checkbox = @("is_active")
  }
  seller_role = @{
    select = @("sector")
    text = @()
    checkbox = @()
  }
}

$headers = @{
  Authorization = "Bearer $($SourceApiKey.Trim())"
  Accept = "application/json"
  "Content-Type" = "application/json"
}

$outputRoot = Join-Path $PSScriptRoot "..\..\..\..\outputs\attio_migration"
$null = New-Item -ItemType Directory -Force -Path $outputRoot

function Invoke-AttioRequest {
  param(
    [ValidateSet("Get", "Post", "Patch", "Delete")][string]$Method,
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
    if ($page.Count -lt 500) { return $all }
  }
}

function Get-Titles {
  param([object]$Values, [string]$Slug)
  return @(
    $Values.$Slug |
      Where-Object { $null -eq $_.active_until } |
      ForEach-Object { if ($_.option.title) { [string]$_.option.title } else { [string]$_.value } } |
      Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
  )
}

function Get-Scalar {
  param([object]$Values, [string]$Slug)
  $item = @($Values.$Slug) | Where-Object { $null -eq $_.active_until } | Select-Object -First 1
  if ($null -eq $item) { return $null }
  if ($item.option.title) { return [string]$item.option.title }
  if ($null -ne $item.value) { return $item.value }
  return $null
}

$manifestPath = Join-Path $BackupDir "manifest.json"
if (-not (Test-Path $manifestPath)) { throw "No manifest.json in $BackupDir -- not a backup directory." }
$manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json

$organizationsObject = Invoke-AttioRequest -Method Get -Path "/objects/organizations"
$connectedWorkspaceId = [string]$organizationsObject.data.id.workspace_id
if ($connectedWorkspaceId -ne [string]$manifest.workspace_id) {
  throw ("Workspace mismatch. Backup is from {0} but connected to {1}." -f `
    $manifest.workspace_id, $connectedWorkspaceId)
}

Write-Host ("Backup {0}, captured {1}" -f $manifest.run_id, $manifest.captured_at_utc)

$report = [ordered]@{}
foreach ($entity in $Entities) {
  $file = Join-Path $BackupDir "$entity.json"
  if (-not (Test-Path $file)) { Write-Warning "No $entity.json in the backup; skipping."; continue }

  $backup = Get-Content $file -Raw | ConvertFrom-Json
  $backupById = @{}
  foreach ($row in @($backup.rows)) { $backupById[[string]$row.id.entry_id] = $row }

  $live = Get-PagedData -Path "/lists/$entity/entries/query"
  $liveIds = [Collections.Generic.HashSet[string]]::new()
  foreach ($row in $live) { $null = $liveIds.Add([string]$row.id.entry_id) }

  $fields = $restorableFields[$entity]
  $optionMaps = @{}
  foreach ($field in $fields.select) {
    try {
      $response = Invoke-AttioRequest -Method Get -Path "/lists/$entity/attributes/$field/options"
    } catch {
      # The attribute may have been archived since the capture -- that is a
      # legitimate state, and its values simply cannot be restored.
      Write-Warning "$entity/$field is not readable (archived?); its values will not be restored."
      continue
    }
    $map = @{}
    foreach ($option in @($response.data | Where-Object { -not $_.is_archived })) {
      $map[[string]$option.title] = [string]$option.id.option_id
    }
    $optionMaps[$field] = $map
  }

  $patches = [Collections.Generic.List[object]]::new()
  $unrestorable = [Collections.Generic.List[string]]::new()
  foreach ($entryId in $backupById.Keys) {
    if (-not $liveIds.Contains($entryId)) { $unrestorable.Add($entryId); continue }
    $values = $backupById[$entryId].entry_values
    $payload = @{}

    foreach ($field in $fields.select) {
      if (-not $optionMaps.ContainsKey($field)) { continue }
      $titles = @(Get-Titles -Values $values -Slug $field)
      $ids = [Collections.Generic.List[string]]::new()
      foreach ($title in $titles) {
        if (-not $optionMaps[$field].ContainsKey($title)) {
          throw "$entity/$field has no option '$title' any more. Re-add it before restoring."
        }
        $ids.Add($optionMaps[$field][$title])
      }
      $payload[$field] = @($ids)
    }
    foreach ($field in $fields.text) {
      $payload[$field] = Get-Scalar -Values $values -Slug $field
    }
    foreach ($field in $fields.checkbox) {
      $payload[$field] = Get-Scalar -Values $values -Slug $field
    }

    $patches.Add([ordered]@{ entry_id = $entryId; values = $payload })
  }

  $createdSince = @($live | Where-Object { -not $backupById.ContainsKey([string]$_.id.entry_id) })

  $report[$entity] = [ordered]@{
    in_backup = @($backup.rows).Count
    live_now = $live.Count
    to_patch = $patches.Count
    created_since_capture = $createdSince.Count
    deleted_since_capture_unrestorable = $unrestorable.Count
  }

  Write-Host ""
  Write-Host ("=== {0} ===" -f $entity)
  Write-Host ("  in backup {0} | live {1} | patch {2} | created since {3} | gone {4}" -f `
    @($backup.rows).Count, $live.Count, $patches.Count, $createdSince.Count, $unrestorable.Count)
  if ($unrestorable.Count -gt 0) {
    Write-Warning ("{0} {1} entries in the backup no longer exist and CANNOT be recreated -- " +
      "Attio would mint new ids and break the foreign keys pointing at the old ones." -f `
      $unrestorable.Count, $entity)
  }

  if (-not $Apply) {
    foreach ($entry in $createdSince) {
      Write-Host ("  DRY RUN: would DELETE {0}" -f [string]$entry.id.entry_id)
    }
    continue
  }

  foreach ($patch in $patches) {
    Invoke-AttioRequest -Method Patch -Path "/lists/$entity/entries/$($patch.entry_id)" `
      -Body @{ data = @{ entry_values = $patch.values } } | Out-Null
  }
  Write-Host ("  patched {0}" -f $patches.Count)

  if ($DeleteCreatedSince) {
    foreach ($entry in $createdSince) {
      $entryId = [string]$entry.id.entry_id
      # Never delete anything the backup did not account for. The set difference
      # above already guarantees it, restated here because this is the one call
      # in this toolchain that destroys data.
      if ($backupById.ContainsKey($entryId)) { continue }
      Invoke-AttioRequest -Method Delete -Path "/lists/$entity/entries/$entryId" | Out-Null
    }
    Write-Host ("  deleted {0}" -f $createdSince.Count)
  } elseif ($createdSince.Count -gt 0) {
    Write-Warning ("{0} {1} entries were created since the capture and were left in place. " +
      "Pass -DeleteCreatedSince to remove them." -f $createdSince.Count, $entity)
  }
}

$summary = [ordered]@{
  generated_at_utc = [DateTime]::UtcNow.ToString("o")
  backup_run_id = $manifest.run_id
  backup_captured_at = $manifest.captured_at_utc
  mode = if ($Apply) { if ($DeleteCreatedSince) { "apply+delete" } else { "apply" } } else { "dry-run" }
  entities = $report
}
[IO.File]::WriteAllText(
  (Join-Path $outputRoot "restore-plan.json"),
  ($summary | ConvertTo-Json -Depth 40),
  [Text.UTF8Encoding]::new($false)
)

$summary | Format-List
Write-Host "Plan: $outputRoot\restore-plan.json"
