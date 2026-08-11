param(
  [string]$RepositoryRoot = (Get-Location).Path
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath $RepositoryRoot).Path

function Relative-Path([string]$Path) {
  $resolved = (Resolve-Path -LiteralPath $Path).Path
  if (-not $resolved.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Path is outside repository root: $resolved"
  }
  $resolved.Substring($root.Length).TrimStart("\", "/").Replace("\", "/")
}

$terraformFiles = Get-ChildItem -LiteralPath $root -Recurse -File |
  Where-Object {
    $_.Extension -eq ".tf" -and
    $_.FullName -notmatch "[\\/]\.terraform[\\/]"
  } |
  Sort-Object FullName

$markdownFiles = Get-ChildItem -LiteralPath $root -Recurse -File |
  Where-Object {
    $_.Extension -eq ".md" -and
    $_.FullName -notmatch "[\\/]\.git[\\/]"
  } |
  Sort-Object FullName

$resources = foreach ($file in $terraformFiles) {
  $lineNumber = 0
  foreach ($line in Get-Content -LiteralPath $file.FullName) {
    $lineNumber++
    if ($line -match '^\s*(resource|data|module|variable|output)\s+"([^"]+)"(?:\s+"([^"]+)")?') {
      [pscustomobject]@{
        Kind = $Matches[1]
        Type = $Matches[2]
        Name = $Matches[3]
        File = Relative-Path $file.FullName
        Line = $lineNumber
      }
    }
  }
}

$architectureTerms = @(
  "aws_region", "vpc_cidr", "public_subnet_cidr", "private_subnet_cidr",
  "instance_type", "ami_architecture", "root_volume_size", "expose_n8n_port",
  "backend ""s3""", "bucket", "key", "region", "use_lockfile"
)

Write-Output "# Terraform documentation inventory"
Write-Output ""
Write-Output "Repository: $root"
Write-Output "Terraform files: $($terraformFiles.Count)"
Write-Output "Markdown files: $($markdownFiles.Count)"
Write-Output ""
Write-Output "## Terraform declarations"
$resources | Format-Table Kind, Type, Name, File, Line -AutoSize

Write-Output "## Architecture values"
foreach ($term in $architectureTerms) {
  $matches = Select-String -Path $terraformFiles.FullName -Pattern $term -SimpleMatch
  foreach ($match in $matches) {
    "{0}:{1}: {2}" -f (Relative-Path $match.Path), $match.LineNumber, $match.Line.Trim()
  }
}

Write-Output ""
Write-Output "## Documentation files"
$markdownFiles | ForEach-Object { Relative-Path $_.FullName }
