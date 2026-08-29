param(
  [ValidateSet("organizations","person","deal")]
  [string[]]$Objects=@("organizations","person","deal"),
  [string]$SourceApiKey=$env:SOURCE_ATTIO_API_KEY,
  [string]$DevApiKey=$env:SOURCE_ATTIO_API_KEY,
  [int]$Limit=10,
  [string]$DevDealOwnerWorkspaceMemberId,
  [string]$Confirmation,
  [switch]$Parallel,
  [ValidateRange(1,8)]
  [int]$Workers=4,
  [switch]$ExistingDealsOnly,
  [switch]$DeleteOrphaned,
  [switch]$MigrateMandates,
  [switch]$Apply
)
$ErrorActionPreference="Stop"
if([string]::IsNullOrWhiteSpace($SourceApiKey)){$SourceApiKey=[Environment]::GetEnvironmentVariable("SOURCE_ATTIO_API_KEY","User")}
if([string]::IsNullOrWhiteSpace($DevApiKey)){$DevApiKey=[Environment]::GetEnvironmentVariable("SOURCE_ATTIO_API_KEY","User")}
if([string]::IsNullOrWhiteSpace($SourceApiKey)){throw "Missing SOURCE_ATTIO_API_KEY."}
if([string]::IsNullOrWhiteSpace($DevApiKey)){throw "Missing SOURCE_ATTIO_API_KEY."}
if($Limit-lt0){throw "Limit cannot be negative. Use 0 for all records."}
if($Parallel-and$Limit-ne0){throw "Parallel mode processes complete objects and requires -Limit 0."}
if($DeleteOrphaned-and($Objects.Count-ne1-or$Objects[0]-ne"deal")){
  throw "-DeleteOrphaned only supports -Objects deal."
}
if($MigrateMandates-and($Objects.Count-ne1-or$Objects[0]-ne"deal")){
  throw "-MigrateMandates only supports -Objects deal."
}
if($Apply){
  if($DeleteOrphaned){
    if($Confirmation-ne"DELETE_ORPHANED_DEALS_FROM_DEV"){throw "Apply with -DeleteOrphaned requires Confirmation DELETE_ORPHANED_DEALS_FROM_DEV."}
  }elseif($Confirmation-ne"APPLY_SELECTED_OBJECTS_TO_DEV"){
    throw "Apply requires Confirmation APPLY_SELECTED_OBJECTS_TO_DEV."
  }
}
foreach($object in $Objects){
  Write-Host ""
  Write-Host "== Schema preflight: $object =="
  $schemaArgs=@{Entities=@($object);DevApiKey=$DevApiKey;SourceApiKey=$SourceApiKey}
  if($Apply-and$object-eq"deal"){$schemaArgs.FailOnDrift=$true}
  & (Join-Path $PSScriptRoot "ensure-schema.ps1") @schemaArgs
  if(-not$?){throw "$object schema preflight failed."}
}
foreach($object in $Objects){
  Write-Host ""
  Write-Host "== Sync object: $object =="
  if($object-eq"deal"){
    $args=@{SourceApiKey=$SourceApiKey;DevApiKey=$DevApiKey;Limit=$Limit}
    if($ExistingDealsOnly){$args.ExistingOnly=$true}
    if(-not[string]::IsNullOrWhiteSpace($DevDealOwnerWorkspaceMemberId)){$args.DevOwnerWorkspaceMemberId=$DevDealOwnerWorkspaceMemberId}
    if($DeleteOrphaned){
      $args.DeleteOrphaned=$true
      if($Apply){$args.Apply=$true;$args.Confirmation="DELETE_ORPHANED_DEALS_FROM_DEV"}
    }elseif($Apply){
      $args.Apply=$true;$args.Confirmation=if($Limit-eq0){"APPLY_ALL_DEALS_TO_DEV"}else{"APPLY_DEALS_TO_DEV"}
    }
    if($MigrateMandates){$args.MigrateMandates=$true}
    $args.Task="deals"
    & (Join-Path $PSScriptRoot "_internal\objects.ps1") @args
  }else{
    if($Parallel){
      $args=@{Object=$object;SourceApiKey=$SourceApiKey;DevApiKey=$DevApiKey;Workers=$Workers}
      if($Apply){$args.Apply=$true}
      $args.Task="parallel"
      & (Join-Path $PSScriptRoot "_internal\objects.ps1") @args
    }else{
      $args=@{Object=$object;SourceApiKey=$SourceApiKey;DevApiKey=$DevApiKey;Limit=$Limit}
      if($Apply){$args.Apply=$true}
      $args.Task="record"
      & (Join-Path $PSScriptRoot "_internal\objects.ps1") @args
    }
  }
  if(-not$?){throw "$object sync failed."}
}
if($Apply){Write-Host "Unified selected-object apply complete."}else{Write-Host "Unified selected-object dry-run complete. No Attio records were written."}
