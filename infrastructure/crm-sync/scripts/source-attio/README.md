# SOURCE Attio Within-Workspace Migration

This folder migrates the SOURCE Attio workspace's own native Companies,
People, Deals, `buyer_brain`, and `valuation_tool_leads` into **new custom
objects/lists built in that same workspace** (`organizations`, `person`,
`deal` ["Deals_V2"], `buyer_role`, `seller_role`). Unlike
`../dev-attio` (which migrates SOURCE into a *separate* DEV workspace), the
read side and the write side here are the same workspace, via the same
`SOURCE_ATTIO_API_KEY` for both. The native objects/lists are never written
to -- only ever read from.

Because SOURCE and target are the same workspace, there is no
SOURCE-to-DEV workspace-member crosswalk: a Deal's `owner` (a real
actor-reference in SOURCE) is already valid on the target and is passed
through directly; Organization/Person's `relationship_owner` (a plain text
name in SOURCE, not a real reference) is resolved against this workspace's
own live member list instead of a hardcoded name-to-id table.

## Command surface

Run only these public scripts:

| Script | Responsibility |
| --- | --- |
| `sync-all-within-source.ps1` | Single entry point for a full migration run. Wraps `sync-objects.ps1`/`sync-lists.ps1`/`backfill-notes.ps1` in the required dependency order (`organizations -> person -> buyer_role -> seller_role -> deal -> note`), fails fast on the first error, and accepts `-Entities` to run a subset instead of everything. `-Entities deal -DeleteOrphaned` deletes target Deal records whose `legacy_attio_id` no longer exists in SOURCE. Idempotent, safe to re-run. |
| `ensure-schema.ps1` | Validate or create the approved target object/list schema. Does not migrate records. |
| `sync-objects.ps1` | Migrate Organizations, Persons, and Deal. |
| `sync-lists.ps1` | Migrate Buyer Role and Seller Role. |
| `backfill-seller-intake-source.ps1` | One-off backfill, carried over from `dev-attio` -- likely not needed for a fresh migration; verify before running. |
| `backfill-notes.ps1` (its own note timestamp field is `note_created_at`, not `created_at` -- Attio reserves that slug for a protected system attribute on every custom object; writing to it 400s with `system_edit_unauthorized`, confirmed live 2026-08-28) | One-off backfill for the `note` custom object (plural noun "Unified Notes" -- slug is `note`, not `notes`, since Attio reserves `notes` for its own native per-record Notes feature; proposed unified notes table, see `config/target-schema.json`'s `Notes` entry). Populates it from native Companies'/People's own Notes panel (`GET /v2/notes`) plus the migrated `buyer_role` list's `notes` text field -- SOURCE Attio only, no Postgres. Both `note_type=Manual` and `note_type=Meeting` are migrated (nothing is filtered by type); Meeting is auto-detected by content (a `notes.granola.ai` transcript link, confirmed live against real Granola-sourced notes), everything else is Manual. The `note` object itself must already exist (created manually in the UI); this script only manages its attributes and records. Uses `-Workers` (runspace pool) to parallelize the native-notes fetch. Idempotent via a `legacy_note_id` key, safe to re-run. Wired into `sync-all-within-source.ps1` as the last entity in the pipeline. |
| `validate-attio.ps1` | Compare SOURCE counts with canonical target counts after migration. Read-only. |
| `validate-notes.ps1` | Independently re-derives the expected Manual+Meeting note set straight from SOURCE (same classification AND same organizations/person eligibility filter as `backfill-notes.ps1` -- a note whose parent Company/Person isn't migrated yet is excluded from "expected", not reported as missing) and diffs it against what's actually in the `note` object, by `legacy_note_id`, `note_type`, and `content`. Reports specific missing/extra/mismatched records, not just aggregate counts. Read-only. |

### Full migration order (`sync-all-within-source.ps1`)

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\workflows\crm-sync\scripts\source-attio\sync-all-within-source.ps1                            # dry run, all entities
.\workflows\crm-sync\scripts\source-attio\sync-all-within-source.ps1 -Parallel -Workers 8 -Apply # full apply
.\workflows\crm-sync\scripts\source-attio\sync-all-within-source.ps1 -Entities deal              # dry run a subset only
```

`-Parallel` only actually speeds up `organizations`, `person`, and
`buyer_role` today (the only entities with a parallel-apply path
implemented) -- `seller_role` and `deal` always run single-threaded
regardless of the flag.

`_internal/schema.ps1`, `_internal/objects.ps1`, and `_internal/lists.ps1`
contain consolidated implementation logic and are not run directly. The JSON
files in `config/` define workspace decisions, field mappings, and target
schema -- this folder's copy is retargeted for the same-workspace scenario
and should not be assumed to match `../dev-attio/config/`.

## Prerequisites

The new `organizations`, `person`, and `deal` (title "Deals_V2") custom
objects must already exist in the workspace -- created manually first, this
script only manages their attributes, not their creation. The pipeline
Status field on `deal` (its stage board) also must exist manually first;
its slug is discovered live by attribute type, not assumed to be `stage`.

Set this environment variable without printing or committing its value:

```powershell
$env:SOURCE_ATTIO_API_KEY = "<source-key-with-write-access>"
```

Every apply verifies the connected workspace ID matches
`config/migration-decisions.json`'s `dev_workspace_id`
(`176eb4b0-40a9-419b-b363-784b596a6bbc` -- the SOURCE workspace's own id,
used here as a same-workspace self-consistency check). Never place
credentials in Git, screenshots, logs, or documentation.

## Migration order

```text
Schema preflight
  -> Organizations
  -> Persons
  -> Deal
  -> Buyer Role
  -> Seller Role
  -> Validation
```

### 1. Schema dry-run

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\workflows\crm-sync\scripts\source-attio\ensure-schema.ps1
```

Review missing attributes, wrong types/cardinality, list parents, relationship
targets, and option drift. Apply approved schema changes only when needed:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\workflows\crm-sync\scripts\source-attio\ensure-schema.ps1 `
  -Apply
```

### 2. Object dry-run

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\workflows\crm-sync\scripts\source-attio\sync-objects.ps1 `
  -Limit 0 `
  -Parallel `
  -Workers 4 `
  -ExistingDealsOnly
```

The dry-run reads SOURCE (native) and the target (new custom objects),
matches by `legacy_attio_id`, resolves relationships, builds payloads in
memory, and reports proposed creates, updates, conflicts, and errors. It
performs no writes.

### 3. Object apply

Run only after the object dry-run has no blocking errors:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\workflows\crm-sync\scripts\source-attio\sync-objects.ps1 `
  -Limit 0 `
  -Parallel `
  -Workers 4 `
  -ExistingDealsOnly `
  -Apply `
  -Confirmation APPLY_SELECTED_OBJECTS_TO_DEV
```

Objects use `PUT` for an existing target record and `POST` for a missing
record. The SOURCE record ID is stored in the target's `legacy_attio_id`;
the target's own record ID is its own identity.

### 4. List dry-run

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\workflows\crm-sync\scripts\source-attio\sync-lists.ps1 `
  -Limit 0 `
  -Workers 3
```

### 5. Apply lists one at a time

Buyer Role:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\workflows\crm-sync\scripts\source-attio\sync-lists.ps1 `
  -Lists buyer_role -Limit 0 -Workers 3 -Apply `
  -Confirmation APPLY_ALL_BUYER_ROLE_TO_DEV
```

Seller Role:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\workflows\crm-sync\scripts\source-attio\sync-lists.ps1 `
  -Lists seller_role -Limit 0 -Apply `
  -Confirmation APPLY_ALL_SELLER_ROLE_TO_DEV
```

Existing list entries use `PATCH`; missing entries use `POST`. Each list entry
is attached to its resolved target Organization parent.

### 6. Final validation

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\workflows\crm-sync\scripts\source-attio\validate-attio.ps1
```

The validator is read-only. It compares SOURCE and target object counts. For
lists it reports the raw SOURCE count and the canonical unique-parent count,
because duplicate SOURCE entries for the same parent intentionally become one
target list entry. It also fails on missing SOURCE parents, duplicate target
list parents, a count mismatch, or connection to the wrong workspace.

## Mapping rules to highlight

- SOURCE Companies -> custom `organizations`.
- SOURCE People -> custom `person`.
- SOURCE `associated_company` -> Deal `seller_id`.
- `buyer_id` remains blank on every migrated Deal -- SOURCE `deals` has no
  buyer-referencing field at all, so every migrated Deal is `deal_type =
  Sell-side` by construction.
- Deal value: SOURCE's native `value` is copied straight into the custom
  `deal` object's own `deal_value` field, no currency conversion. Previously
  converted AED->USD via a fixed peg (assuming SOURCE's native `value` was
  always a real AED figure, since DEV's own copy of that field is an
  Attio-locked System attribute permanently stuck at AED) -- dropped
  2026-08-28 after confirming SOURCE's copy has since been manually switched
  to USD for at least some records (DEV's stayed AED-locked and unaffected),
  making per-record currency indistinguishable. See `MoneyValue` in
  `_internal/objects.ps1` for the full history.
- Organization/Person Relationship Status is an optional single select.
  When SOURCE has more than one simultaneously-active value, the one with
  the latest `active_from` wins (`Get-NormalizedRelationshipStatus`); throws
  rather than guessing if timestamps are missing or tied. `client_type`
  (2026-08-28) uses the same latest-wins resolution (`Get-LatestClientType`),
  without Relationship Status's fixed Warm/Cold/Closed vocabulary remap --
  the winning SOURCE title is used as-is.
- Deal readiness fields are optional Booleans.
- `backfill-notes.ps1` upserts, not create-only (2026-08-28): a note whose
  `legacy_note_id` already exists gets its content (and everything else)
  updated in place via `PUT` if SOURCE's content has since changed -- e.g. a
  Granola meeting thread gaining more detail after the fact -- rather than
  staying stale forever. Found via `validate-notes.ps1` catching content
  mismatches on notes the backfill had already "successfully" created.
- List duplicates are canonicalized by parent before writing.
- Ambiguous relationships remain blank and are reported; names are not IDs.

## Outputs and recovery

Plans, summaries, worker logs, and conflict reports are written beneath
`scripts/outputs/attio_migration/`. They are migration evidence, not a staging
database. SOURCE/target records are otherwise transformed in process memory.

All commands default to dry-run. Do not interrupt an apply unless necessary;
if interrupted, rerun from the beginning because writes are idempotent.
