param(
  [ValidateSet("organizations","person","deal","buyer_role","seller_role")]
  [string[]]$Entities=@("organizations","person","deal","buyer_role","seller_role"),
  [string]$SourceApiKey=$env:SOURCE_ATTIO_API_KEY,
  [string]$DevApiKey=$env:SOURCE_ATTIO_API_KEY,
  [switch]$FailOnDrift,
  [switch]$Apply
)
$ErrorActionPreference="Stop"
foreach($entity in $Entities){
  $path=Join-Path $PSScriptRoot "_internal\schema.ps1"
  $args=@{Entity=$entity;DevApiKey=$DevApiKey;SourceApiKey=$SourceApiKey}
  if($FailOnDrift){$args.FailOnDrift=$true}
  if($Apply){$args.Apply=$true}
  & $path @args
  if(-not$?){throw "$entity schema operation failed."}
}
