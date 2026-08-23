---
name: sync-crm-schema-docs
description: Keep every CRM schema document in sync whenever an Attio DEV attribute/list/stage or a Postgres deals/mandates/etc. column changes — the ER diagram, the published "Wusool Schema Handover" artifact, CLIENT_SCHEMA_OVERVIEW.md, CRM_MIGRATION_GUIDE.md, scripts/README.md, and database/README.md. Use immediately after any change to workflows/crm-sync/scripts/_internal/schema.ps1, migration-decisions.json, target-schema.json, a Postgres model in database/wusool_db/models/, or a new Alembic migration — before ending the session, not as a separate later cleanup.
---

# Sync CRM Schema Docs

Sibling of `sync-project-docs` (repo-wide READMEs + `docs/PROGRESS.md`) and
`sync-terraform-docs` (Terraform docs). This skill owns everything that
describes the **CRM data model itself** — Attio DEV schema and its Postgres
mirror — across five different places that do not update themselves and
silently drift out of sync with each other otherwise.

## When to run this

Any of these should trigger it, in the same session as the change, not
deferred:

- A new/renamed/retyped Attio attribute, list, or pipeline stage (via
  `ensure-schema.ps1` / `_internal/schema.ps1`, or a direct API call)
- An entry added to `workflows/crm-sync/scripts/config/migration-decisions.json`
  (crosswalk, alias map, deferred backfill) or `target-schema.json`
- A new flag/behavior added to `objects.ps1`/`lists.ps1` (e.g. `-DeleteOrphaned`,
  `-MigrateMandates`)
- A new/changed column in `database/wusool_db/models/*.py` and its Alembic
  migration
- A data backfill that changes what a field means or how confidently it's
  populated (e.g. "all 58 pre-existing Deals are now `Sell-side`")

## The five things to update, every time

1. **`workflows/crm-sync/docs/CLIENT_SCHEMA_OVERVIEW.md`** — the detailed
   field-by-field reference (Attio schema + PostgreSQL schema sections). Add
   new fields to the relevant entity's table with type/ownership/relationship;
   correct any row whose behavior changed (e.g. a crosswalk fix); mark a
   retired object/list clearly (see the Mandate section as the template: a
   `retired YYYY-MM-DD` marker in the heading, one paragraph explaining why,
   table kept for historical reference).

2. **`workflows/crm-sync/docs/CRM_MIGRATION_GUIDE.md`** — the coarse overview:
   data-mapping table, scripts table, safety notes. Update only what changed
   at this altitude; the detailed version belongs in
   `CLIENT_SCHEMA_OVERVIEW.md`, not duplicated here.

3. **`workflows/crm-sync/scripts/README.md`** and **`database/README.md`** —
   whichever side changed (Attio-facing scripts vs. Postgres). Check every
   command example, flag list, and mapping-rules bullet still matches the
   actual script/model — these are read and run literally, so a stale flag
   name or wrong assumption (e.g. "buyer_id remains blank") actively misleads.

4. **`workflows/crm-sync/docs/Database_Architecture_ER_Diagram_Most_Latest.drawio`**
   — the canonical ER diagram (plain XML, hand-editable — grep for the
   entity's swimlane `value=` to find its header cell, then its child field
   rows by `parent="<that cell's id>"`). Add new field rows in the entity's
   accent color, extend the swimlane's `height` to fit (check what sits
   below it first — `grep 'x="<same x>"'` across the file — before growing
   into another box), mark a retired object with a dashed grey swimlane
   (`dashed=1;fillColor=#999999;strokeColor=#999999`) and " — RETIRED
   YYYY-MM-DD" in its title, same as the artifact and the overview doc.
   Never leave this file behind when the artifact or overview doc changes —
   it's the one a first-time reader opens first.

5. **The published "Wusool Schema Handover" artifact** — find its URL with
   `Artifact({action: "list"})` (do not guess or hardcode it, it can change).
   Fetch it with `WebFetch`, strip the injected frame-runtime `<head>`
   wrapper (everything up to and including `</head><body>` on line 1 — the
   real source starts at the following `<title>...</title>`), edit the
   relevant entity section(s) the same way as `CLIENT_SCHEMA_OVERVIEW.md`
   (it's the same content, different medium), then republish with
   `Artifact({action: "publish", file_path: ..., url: "<the same URL>",
   favicon: "📋"})` — passing `url` is what updates it in place instead of
   forking a new artifact.

## Order and consistency rules

- Do (1)-(3) as a set — they're prose describing the same fields, keep their
  wording and the "why" consistent (a rename in one and not the others is
  the exact drift this skill exists to prevent).
- Do (4) and (5) directly from the *already-updated* (1)-(3), not
  independently re-derived from code — they should read as the same content
  in a different shape, not a second opinion.
- A retirement (an object/list no longer synced) gets the *same* marker
  language and date everywhere: heading badge, callout/paragraph explaining
  why, historical table/rows kept, never deleted outright in the same pass
  that retires them.
- If a change is Attio-only (no Postgres model touched), skip
  `database/README.md` and the Postgres section of `CLIENT_SCHEMA_OVERVIEW.md`
  — don't invent a Postgres-side note for something that didn't change there.
- If unsure whether a claim is now stale, verify against the live schema
  (`ensure-schema.ps1` dry run, or a direct Attio `GET .../attributes` call)
  before writing it — do not carry forward a guess from chat history.

## After updating

Report, in one short list, exactly which of the five were touched and which
were skipped (and why) — the same shape as `sync-project-docs`'s reporting
rule. If Terraform or other repo-wide docs also need `sync-project-docs` or
`sync-terraform-docs`, say so rather than doing their job here.
