# SOURCE Attio to DEV Attio Migration

This folder contains the canonical, one-way migration from the legacy SOURCE
Attio workspace to the DEV Wusool Capital workspace. SOURCE is always
read-only. All mutations are guarded and target DEV only.

## Command surface

Run only these four public scripts:

| Script | Responsibility |
| --- | --- |
| `ensure-schema.ps1` | Validate or create the approved DEV object/list schema. Does not migrate records. |
| `sync-objects.ps1` | Migrate Organizations, Persons, and Deals. |
| `sync-lists.ps1` | Migrate Buyer Role, Seller Role, and Mandates. |
| `validate-attio.ps1` | Compare SOURCE counts with canonical DEV counts after migration. Read-only. |

`_internal/schema.ps1`, `_internal/objects.ps1`, and `_internal/lists.ps1`
contain consolidated implementation logic and are not run directly. The JSON
files in `config/` define workspace decisions, field mappings, and target
schema.

## Prerequisites

Set these environment variables without printing or committing their values:

```powershell
$env:SOURCE_ATTIO_API_KEY = "<source-read-key>"
$env:DEV_ATTIO_API_KEY = "<dev-write-key>"
```

Every apply verifies DEV workspace ID
`c9ef3cda-2501-4d19-b7da-1273700721e5`. Never place credentials in Git,
screenshots, logs, or documentation.

## Migration order

```text
Schema preflight
  -> Organizations
  -> Persons
  -> Deals
  -> Buyer Role
  -> Seller Role
  -> Mandates
  -> DEV validation
  -> PostgreSQL sync
```

### 1. Schema dry-run

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\attio\ensure-schema.ps1
```

Review missing attributes, wrong types/cardinality, list parents, relationship
targets, and option drift. Apply approved schema changes only when needed:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\attio\ensure-schema.ps1 `
  -Apply
```

### 2. Object dry-run

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\attio\sync-objects.ps1 `
  -Limit 0 `
  -Parallel `
  -Workers 4 `
  -ExistingDealsOnly
```

The dry-run reads SOURCE and DEV, matches by `legacy_attio_id`, resolves
relationships, builds payloads in memory, and reports proposed creates,
updates, conflicts, and errors. It performs no writes.

### 3. Object apply

Run only after the object dry-run has no blocking errors:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\attio\sync-objects.ps1 `
  -Limit 0 `
  -Parallel `
  -Workers 4 `
  -ExistingDealsOnly `
  -Apply `
  -Confirmation APPLY_SELECTED_OBJECTS_TO_DEV
```

Objects use `PUT` for an existing DEV record and `POST` for a missing record.
The SOURCE record ID is stored in DEV `legacy_attio_id`; the DEV record ID
remains DEV identity.

### 4. List dry-run

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\attio\sync-lists.ps1 `
  -Limit 0 `
  -Workers 3
```

### 5. Apply lists one at a time

Buyer Role:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\attio\sync-lists.ps1 `
  -Lists buyer_role -Limit 0 -Workers 3 -Apply `
  -Confirmation APPLY_ALL_BUYER_ROLE_TO_DEV
```

Seller Role:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\attio\sync-lists.ps1 `
  -Lists seller_role -Limit 0 -Apply `
  -Confirmation APPLY_ALL_SELLER_ROLE_TO_DEV
```

Mandates:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\attio\sync-lists.ps1 `
  -Lists mandates -Limit 0 -Apply `
  -Confirmation APPLY_ALL_MANDATES_TO_DEV
```

Existing list entries use `PATCH`; missing entries use `POST`. Each list entry
is attached to its resolved DEV Organization parent.

### 6. Final SOURCE to DEV validation

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\attio\validate-attio.ps1
```

The validator is read-only. It compares SOURCE and DEV object counts. For
lists it reports the raw SOURCE count and the canonical unique-parent count,
because duplicate SOURCE entries for the same parent intentionally become one
DEV list entry. It also fails on missing SOURCE parents, duplicate DEV list
parents, a count mismatch, or connection to the wrong DEV workspace.

## Expected canonical DEV counts

Use these as reconciliation evidence, not hard-coded migration limits:

| Entity | Expected count |
| --- | ---: |
| Organizations | 3,040 |
| Persons | 4,329 |
| Deals | 48 |
| Buyer Role | 264 |
| Seller Role | 172 |
| Mandates | 2 |

## Mapping rules to highlight

- SOURCE Companies -> custom DEV `organizations`.
- SOURCE People -> custom DEV `person`.
- SOURCE `associated_company` -> DEV Deal `seller_id`.
- Existing Deal `buyer_id` remains blank.
- Organization/Person Relationship Status is an optional single select.
- Deal readiness fields are optional Booleans.
- Exclusivity start/end dates are preserved separately.
- List duplicates are canonicalized by parent before writing.
- Ambiguous relationships remain blank and are reported; names are not IDs.

## Outputs and recovery

Plans, summaries, worker logs, and conflict reports are written beneath
`outputs/attio_migration/`. They are migration evidence, not a staging
database. SOURCE/DEV records are otherwise transformed in process memory.

All commands default to dry-run. Do not interrupt an apply unless necessary;
if interrupted, rerun from the beginning because writes are idempotent.
