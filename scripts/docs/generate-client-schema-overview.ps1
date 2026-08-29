param(
  [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")),
  [string]$OutputPath = (Join-Path $RepoRoot "workflows/crm-sync/docs/CLIENT_SCHEMA_OVERVIEW.md")
)

$ErrorActionPreference = "Stop"
$attioPath = Join-Path $RepoRoot "workflows/crm-sync/scripts/dev-attio/config/target-schema.json"
$sqlDir = Join-Path $RepoRoot "database/sql"
$attio = Get-Content -Raw -LiteralPath $attioPath | ConvertFrom-Json

function Cell([object]$Value) {
  if ($null -eq $Value) { return "-" }
  $text = if ($Value -is [array]) { $Value -join ", " } else { [string]$Value }
  if ([string]::IsNullOrWhiteSpace($text)) { return "-" }
  return $text.Replace("|", "\|").Replace("`r", " ").Replace("`n", " ")
}

function Code([object]$Value) {
  $valueText = Cell $Value
  if ($valueText -eq "-") { return "-" }
  return "``$valueText``"
}

$sqlFiles = Get-ChildItem -LiteralPath $sqlDir -Filter "*.sql" | Sort-Object Name
$tables = [ordered]@{}
$indexes = [System.Collections.Generic.List[string]]::new()

foreach ($file in $sqlFiles) {
  $sql = Get-Content -Raw -LiteralPath $file.FullName
  $matches = [regex]::Matches($sql, '(?ms)^CREATE TABLE IF NOT EXISTS\s+(?<name>[a-zA-Z_][a-zA-Z0-9_]*)\s*\((?<body>.*?)^\);')
  foreach ($match in $matches) {
    $name = $match.Groups['name'].Value
    $columns = [System.Collections.Generic.List[object]]::new()
    $constraints = [System.Collections.Generic.List[string]]::new()
    $insideConstraint = $false
    foreach ($rawLine in ($match.Groups['body'].Value -split "`n")) {
      $line = $rawLine.Trim().TrimEnd(',')
      if (-not $line) { continue }
      if ($insideConstraint) {
        if ($line -match '\)\s*$') { $insideConstraint = $false }
        continue
      }
      if ($line -match '^(CONSTRAINT|UNIQUE|PRIMARY KEY|CHECK|FOREIGN KEY)') {
        $constraints.Add($line)
        if (($line.ToCharArray() | Where-Object { $_ -eq '(' }).Count -gt ($line.ToCharArray() | Where-Object { $_ -eq ')' }).Count) {
          $insideConstraint = $true
        }
        continue
      }
      if ($line -match '^(?<column>[a-zA-Z_][a-zA-Z0-9_]*)\s+(?<type>[a-zA-Z]+(?:\([0-9, ]+\))?(?:\[\])?)(?<rest>.*)$') {
        $rest = $Matches.rest.Trim()
        $columns.Add([pscustomobject]@{
          Name = $Matches.column
          Type = $Matches.type
          Nullable = if ($rest -match '\bNOT NULL\b|\bPRIMARY KEY\b') { 'No' } else { 'Yes' }
          Key = if ($rest -match '\bPRIMARY KEY\b') { 'PK' } elseif ($rest -match '\bUNIQUE\b') { 'Unique' } else { '' }
          Reference = if ($rest -match 'REFERENCES\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^)]+)\)') { "$($Matches[1]).$($Matches[2])" } else { '' }
          Default = if ($rest -match '\bDEFAULT\s+(.+?)(?=\s+REFERENCES\b|\s+PRIMARY KEY\b|\s+UNIQUE\b|$)') { $Matches[1] } else { '' }
        })
      }
    }
    $tables[$name] = [pscustomobject]@{ Name = $name; Columns = $columns; Constraints = $constraints }
  }

  foreach ($indexMatch in [regex]::Matches($sql, '(?im)^CREATE INDEX IF NOT EXISTS\s+(?<name>\S+)\s+ON\s+(?<table>\S+)\s+(?<definition>.+);$')) {
    $indexes.Add("$($indexMatch.Groups['name'].Value)|$($indexMatch.Groups['table'].Value)|$($indexMatch.Groups['definition'].Value)")
  }
}

foreach ($file in $sqlFiles) {
  $sql = Get-Content -Raw -LiteralPath $file.FullName
  foreach ($match in [regex]::Matches($sql, '(?ims)^ALTER TABLE\s+(?<table>\w+)\s+(?<body>(?:ADD COLUMN IF NOT EXISTS\s+\w+\s+[^;]+));')) {
    $tableName = $match.Groups['table'].Value
    if (-not $tables.Contains($tableName)) { continue }
    foreach ($add in [regex]::Matches($match.Groups['body'].Value, '(?i)ADD COLUMN IF NOT EXISTS\s+(?<column>\w+)\s+(?<type>\w+(?:\([^)]+\))?(?:\[\])?)')) {
      $columnName = $add.Groups['column'].Value
      if (-not ($tables[$tableName].Columns.Name -contains $columnName)) {
        $tables[$tableName].Columns.Add([pscustomobject]@{ Name = $columnName; Type = $add.Groups['type'].Value; Nullable = 'Yes'; Key = ''; Reference = ''; Default = '' })
      }
    }
  }
}

$lines = [System.Collections.Generic.List[string]]::new()
function Add([string]$Line = '') { $lines.Add($Line) }

Add '# Wusool CRM and Data Platform Schema'
Add
Add '## Executive overview'
Add
Add 'Wusool uses Attio and PostgreSQL together as one connected data platform. Attio is the working CRM used by the team to manage organizations, people, opportunities, mandates, and relationships. PostgreSQL is the structured data layer used for synchronization, analysis, scoring, automation, research, and document workflows.'
Add
Add 'The two platforms have different responsibilities but share common record identifiers. This allows CRM activity in Attio to connect reliably with enriched and machine-generated information in PostgreSQL.'
Add
Add '### How the platforms work together'
Add
Add '1. The team creates and manages core CRM information in Attio.'
Add '2. Shared records are mirrored into PostgreSQL using Attio identifiers.'
Add '3. PostgreSQL stores analytical, enrichment, event, scoring, and automation data.'
Add '4. Selected operational results can be synchronized back to Attio for use in day-to-day workflows.'
Add
Add '### How to read this document'
Add
Add '- **Platform overview** maps the principal Attio entities to their PostgreSQL tables.'
Add '- **Attio schema** describes the CRM objects, lists, fields, and relationships visible to business users.'
Add '- **PostgreSQL schema** describes the underlying tables, data types, keys, and relationships used by the platform.'
Add '- **Data relationships** explains how records connect across the model.'
Add '- **Data ownership** identifies which platform is responsible for each category of information.'
Add
Add '## Platform overview'
Add
$entityDescriptions = @{
  'Organization' = 'Companies and institutions in the Wusool network'
  'Person' = 'Individual contacts and their organization relationships'
  'User' = 'Authorized workspace members and record owners'
  'buyer_role' = 'Buyer profile, investment criteria, and mandate readiness'
  'seller_role' = 'Seller profile, valuation indicators, and outreach progress'
  'investor_lender_role' = 'Investor or lender preferences and areas of focus'
  'Deal' = 'Transaction opportunities and pipeline progression'
  'Mandate' = 'Buy-side or sell-side engagements and execution progress'
}
Add '| Attio entity | Business purpose | Entity type | PostgreSQL table |'
Add '|---|---|---|---|'
foreach ($entity in $attio.attio_entities) {
  Add "| $(Cell $entity.name) | $(Cell $entityDescriptions[$entity.name]) | $(Cell $entity.attio_kind) | $(Code $entity.postgres_table) |"
}
Add
Add '## Attio schema'
Add
Add 'Attio contains the client-facing CRM records, relationship information, pipeline data, and role-based workflows.'
Add
foreach ($entity in $attio.attio_entities) {
  Add "### $($entity.name)"
  Add
  $metadata = @("Type: $(Cell $entity.attio_kind)")
  if ($entity.attio_slug) { $metadata += "API identifier: $(Code $entity.attio_slug)" }
  if ($entity.parent_object) { $metadata += "Parent: $(Code $entity.parent_object)" }
  Add ($metadata -join ' | ')
  Add
  Add '| Field | Type | Data responsibility | Relationship |'
  Add '|---|---|---|---|'
  foreach ($field in $entity.fields) {
    $relationship = if ($field.target) { $field.target } else { '-' }
    Add "| $(Code $field.slug) | $(Code $field.type) | $(Cell $field.ownership) | $(Cell $relationship) |"
  }
  Add
}

Add '## PostgreSQL schema'
Add
Add 'PostgreSQL stores the CRM mirror, analytical data, automation state, generated documents, scoring outputs, and machine-readable events.'
Add
Add '### PostgreSQL functional areas'
Add
Add '| Area | Tables | Purpose |'
Add '|---|---|---|'
Add '| CRM mirror | `users`, `organizations`, `people`, `deals`, `mandates` | Structured copies of core CRM records |'
Add '| Business roles | `buyer_roles`, `seller_roles`, `investor_lender_roles` | Buyer, seller, investor, and lender-specific information |'
Add '| Activity and pipeline | `activities`, `deal_stage_events`, `signals` | Interactions, deal movements, and market or buyer signals |'
Add '| Intelligence and matching | `buyer_intel`, `seller_financials`, `mandate_targets`, `match_scores` | Research, financial normalization, targeting, and opportunity matching |'
Add '| Knowledge and documents | `documents`, `vertical_kb`, `graph_edges`, `scorecards` | Generated files, sector research, relationship networks, and reporting |'
Add '| Integration operations | `attio_sync_state`, `attio_raw_events` | Synchronization progress and incoming Attio events |'
Add

foreach ($table in $tables.Values) {
  Add "### $($table.Name)"
  Add
  Add '| Column | Type | Nullable | Key | References | Default |'
  Add '|---|---|---:|---|---|---|'
  foreach ($column in $table.Columns) {
    Add "| $(Code $column.Name) | $(Code $column.Type) | $($column.Nullable) | $(Cell $column.Key) | $(Code $column.Reference) | $(Code $column.Default) |"
  }
  if ($table.Constraints.Count -gt 0) {
    Add
    Add '**Table constraints**'
    Add
    foreach ($constraint in $table.Constraints) { Add "- ``$constraint``" }
  }
  Add
}

Add '## Database indexes'
Add
Add '| Index | Table | Definition |'
Add '|---|---|---|'
foreach ($index in $indexes) {
  $parts = $index -split '\|', 3
  Add "| $(Code $parts[0]) | $(Code $parts[1]) | $(Code $parts[2]) |"
}
Add
Add '## Data relationships'
Add
Add '| From | To | Cardinality / rule |'
Add '|---|---|---|'
foreach ($table in $tables.Values) {
  foreach ($column in $table.Columns | Where-Object Reference) {
    Add "| $(Code "$($table.Name).$($column.Name)") | $(Code $column.Reference) | Many-to-one unless constrained unique |"
  }
}
Add
Add 'Notable rules:'
Add
Add '- `deals` allows either an organization buyer or a person buyer, but not both.'
Add '- Role tables are one-to-one with an organization because `org_attio_id` is unique.'
Add '- `mandate_targets` is unique per `(mandate_id, seller_attio_id)` pair.'
Add '- `graph_edges` rejects self-referencing person edges.'
Add
Add '## Data ownership'
Add
Add '| Responsibility | Description |'
Add '|---|---|'
Add '| Attio | Business-managed CRM and relationship data |'
Add '| PostgreSQL | Platform, enrichment, analytical, and automation data |'
Add '| Shared | Operational data synchronized between both platforms |'
Add '| Key | Record identifiers and relationship references |'
Add
Add '## Summary'
Add
Add 'The combined model provides a unified structure for organizations, people, deals, mandates, investor and seller workflows, activities, intelligence, matching, documents, and integrations.'

$outputDirectory = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
Set-Content -LiteralPath $OutputPath -Value ($lines -join "`n") -Encoding utf8
Write-Host "Generated $OutputPath"
