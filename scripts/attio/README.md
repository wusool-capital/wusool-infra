# Attio Migration Scripts

These scripts support the reusable Attio migration path:

```text
Source Attio workspace
-> discover schema, lists, and records
-> map fields
-> create/update DEV Attio
-> sync DEV Attio to PostgreSQL
```

The first script is read-only. It discovers object and list metadata from both
workspaces so mappings are based on real Attio IDs/slugs instead of guesses.

## Required Environment Variables

```powershell
$env:SOURCE_ATTIO_API_KEY = "source-token"
$env:DEV_ATTIO_API_KEY = "dev-token"
```

Do not commit API keys or `.env` files.

## Discovery

Discover both workspaces when both tokens are available:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\attio\discover-attio.ps1
```

Discover only DEV while waiting for source access:

```powershell
$env:DEV_ATTIO_API_KEY = "dev-token"
powershell -ExecutionPolicy Bypass -File .\scripts\attio\discover-attio.ps1 -Workspace dev
```

Outputs are written to:

```text
outputs/attio/source-objects.json
outputs/attio/source-lists.json
outputs/attio/source-object-attributes.json
outputs/attio/source-list-attributes.json
outputs/attio/dev-objects.json
outputs/attio/dev-lists.json
outputs/attio/dev-object-attributes.json
outputs/attio/dev-list-attributes.json
```

After discovery, create the field mapping:

```text
scripts/attio/config/field-mapping.example.json
```

and save the real mapping as:

```text
outputs/attio/field-mapping.json
```

## DEV Legacy IDs

To make source-to-DEV migration rerunnable, DEV Attio records should store the
source record ID in `legacy_attio_id`.

```powershell
$env:DEV_ATTIO_API_KEY = "dev-token"
powershell -ExecutionPolicy Bypass -File .\scripts\attio\ensure-dev-legacy-fields.ps1
```

The script checks and creates `legacy_attio_id` on:

```text
companies
people
deals
scorecards
```

## Core DEV Schema

After source and DEV discovery have run, create the core Wusool DEV schema:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\attio\ensure-dev-core-schema.ps1
```

The script is scoped to:

```text
Objects: companies, people, deals
Lists: buyer_brain, valuation_tool_leads, buy_side_mandates
```

Relationship, actor, and interaction attributes are skipped for explicit review.
After it completes, rerun discovery and comparison.

Deal stages are status values and use a separate API. Sync source deal stages to
DEV before migrating deals:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\attio\ensure-dev-deal-stages.ps1
```

## Source Record Samples

Before writing records into DEV, export a small read-only sample to inspect value
shapes:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\attio\export-attio-records.ps1 -Limit 10
```

Outputs:

```text
outputs/attio/records/companies.sample.json
outputs/attio/records/people.sample.json
outputs/attio/records/deals.sample.json
```

## Company Migration

Run a dry-run first:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\attio\migrate-companies.ps1 -Limit 1
```

Apply one record after reviewing the dry run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\attio\migrate-companies.ps1 -Limit 1 -Apply
```

The script uses `legacy_attio_id` to detect whether a source company already
exists in DEV.

By default it skips select fields because DEV must have matching option values
first. Use `-IncludeSelects` only after option sync/review.

## People Migration

Run a dry-run first:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\attio\migrate-people.ps1 -Limit 1
```

Apply one record:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\attio\migrate-people.ps1 -Limit 1 -Apply
```

People are linked to DEV companies only when the referenced source company has
already been migrated and can be found by `legacy_attio_id`.

## Deal Migration

Run a dry-run first:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\attio\migrate-deals.ps1 -Limit 1
```

Apply one record:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\attio\migrate-deals.ps1 -Limit 1 -Apply
```

Deals are linked to DEV companies only when the referenced source company has
already been migrated and can be found by `legacy_attio_id`.

Currency fields are skipped by default until value formatting is confirmed. Use
`-IncludeCurrency` only after a small test.

## Counts

Check source and DEV record counts:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\attio\count-attio-records.ps1
```

## Core Batch Runner

Run all core object migrations in batches. Dry-run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\attio\run-core-migration.ps1 -BatchSize 100
```

Apply:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\attio\run-core-migration.ps1 -BatchSize 100 -Apply
```

Run only one object:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\attio\run-core-migration.ps1 -Object companies -BatchSize 100 -Apply
```

Run a bounded range:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\attio\run-core-migration.ps1 -Object companies -BatchSize 50 -StartOffset 1000 -MaxRecords 500 -Apply
```

Deals require an owner in DEV. List DEV workspace members:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\attio\list-dev-members.ps1
```

Then set:

```powershell
$env:DEV_ATTIO_OWNER_WORKSPACE_MEMBER_ID = "workspace-member-id"
```
