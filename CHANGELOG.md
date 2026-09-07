# Changelog

Meaningful changes to `wusool-infra` — infrastructure, the Wusool Toolkit
Slack bot, and the Attio ↔ PostgreSQL data platform.

The project has no version tags: every merge to `dev` / `prod` deploys.
Entries are grouped by date, newest first, using the
[Keep a Changelog](https://keepachangelog.com/) categories. For the current
delivered state and outstanding items see
[`docs/handover/README.md`](docs/handover/README.md).

## 2026-09-07 (yet again)

### Fixed

- WusoolScribe 0.4.8: every `ScrollArea` surface (sidebar meeting list,
  settings, folder view, transcript panel, model manager, dialogs) showed a
  duplicate native scrollbar alongside the shadcn/Radix one. Radix hides the
  native bar via a runtime-injected `<style>` tag, which Tauri's nonce'd
  `style-src` CSP silently drops — the same class of issue #117 hit with
  Sonner's stylesheet. The hiding rule is now shipped in `globals.css`
  instead, scoped to `[data-radix-scroll-area-viewport]`.

## 2026-09-07 (even later)

### Changed

- **`meetings` now files a note for every meeting, not just the ones with
  a resolved organization.** The early return that skipped org-less
  meetings entirely (internal/general/investor, or a company that never
  resolved to an Attio org) is removed — `notes.organization_id` was made
  nullable specifically for this case back on 2026-08-29, but the
  meeting-summary pipeline never started using it. Both Postgres and Attio
  now get the note; an org-less Attio note omits the `organization_id`
  key rather than sending an empty reference.
- **Meeting notes now link to the org's active buyer/seller-role row.**
  When a note's meeting is buyer-primary or seller-primary,
  `notes.buyer_role_id`/`seller_role_id` are set to that org's
  most-recently-created *active* `buyer_roles`/`seller_roles` row (never
  both) — new `RoleLookupPort`/`RoleLookup` in `meetings/persistence/`,
  since `buyer_roles`/`seller_roles` have no owning module to wrap. The
  same row's `legacy_entry_id` is sent to Attio's `buyer_role_id`/
  `seller_role_id` text attributes. The link is skipped on both sides
  when the row has no `legacy_entry_id` — `ddl_commands`' inbound note
  sync (`_NOTE_UPSERT`) re-resolves those columns from whatever Attio
  holds on every `note.created`/`note.updated` webhook, so sending a
  Postgres id with nothing on the Attio side would let the next webhook
  silently overwrite it back to NULL.
- **`AttioNoteWriter.push_note` now actually writes `notes.primary_role`**
  (schema added the same day by `b4e1d7c0f3a2`, but nothing wrote it yet)
  — the meeting's seller/buyer/investor/internal/general tag, sent to
  Attio's existing `note.primary_role` select and to the Postgres column,
  both via the shared native `meeting_role` enum.
- **New `meetings.primary_role`**, reusing the same `meeting_role` enum —
  promotes the role tag out of `meetings.metadata` jsonb (where
  `encode_role_metadata` already stashed it) into a queryable column, so
  internal/general meetings can be filtered out of a notes listing without
  needing an org to anchor them. `notes.primary_role` is set from this
  column at publish time.
- **New `meetings.note_id`**, written back once a meeting's note exists,
  so a meeting can be traced to the CRM note it produced. Postgres-only —
  Attio has no meeting object.
- `NotesRepository.create` now runs inside its own savepoint
  (`begin_nested()`). Every meeting reaching the notes insert (not just
  org-having ones, as before) meant a failed insert could otherwise poison
  the whole session and silently roll back the `mark_completed` a few
  statements earlier, stranding the meeting in `summarizing` forever.
- Migration `f5cd5212e82e` (on top of `b4e1d7c0f3a2`): `meetings.primary_role`
  (reusing the `meeting_role` type), `meetings.note_id` + `fk_meetings_note_id`.
  No backfill — both databases were cleared before this change.

## 2026-09-07 (later still)

### Added

- **`notes.primary_role`** — which side the meeting a note came from was
  about, so internal meetings can be filtered out of the Attio UI. A Select
  on Attio's `note` object and the native Postgres enum `meeting_role`
  (migration `b4e1d7c0f3a2`), so both sides can filter rather than only
  string-match.
  - The five option titles are **lowercase** (`seller`, `buyer`, `investor`,
    `internal`, `general`): they are the `MeetingRole` `StrEnum` values
    (`meetings/domain/roles.py`) and the server sends the enum's string
    straight through. Attio select values are case-sensitive, so title-casing
    them there would fail the write or silently create a second set of
    options. Deliberately *not* patterned on the neighbouring `note_type`,
    whose `Manual`/`Meeting` are capitalised.
  - Nullable, with no backfill: a manual note has no role, and neither does
    anything written before today.
  - Wired through both read paths — the webhook upsert
    (`persistence/attio_sync.py`) and the nightly
    `sync-notes-from-source.ps1` — plus the attribute declaration in
    `backfill-notes.ps1`, which owns the `note` object's schema.
  - Nothing writes it yet. `AttioNoteWriter.push_note` would have to take the
    role, which means widening `NoteWriterPort`, and choosing *which* of a
    meeting's reconstructed roles is the primary one — a product decision,
    not a schema one.

## 2026-09-07 (later)

### Changed

- **One SOURCE Attio workspace now serves both environments.** The separate
  DEV workspace is retired; `ATTIO_IS_TEST` says which half a process owns.
  Every server-side Attio create stamps `is_test`, and every ingest path
  skips the other half.
  - `ATTIO_IS_TEST` is a new setting on the `attio` module, deliberately
    independent of `APP_ENV` — Terraform says `dev`/`prod` while
    `.env.example` said `development`, and binding CRM-data correctness to
    environment-name spelling across two vocabularies is the ambiguity to
    avoid. It defaults to `true`, because the two failure directions are not
    symmetric: a prod deploy that forgets it hides new records (loud,
    bounded, reversible), whereas a dev deploy that forgets it writes test
    data into production (silent, unbounded). The deployed environments get
    it from `var.environment` in `modules/toolkit-ec2`, so it cannot be
    forgotten.
  - **Patches never re-assert `is_test`.** It describes where a record came
    from, not who is editing it. A read-before-write guard refuses a
    cross-scope edit instead, and `resolve_role_entry_id` filters by scope
    inside its existing page-through, so the role side costs no extra calls.
  - Role syncs filter the trigger *before* `_fetch_siblings` and filter the
    siblings too. `_reconcile_active_entry` writes back to Attio, so an
    unfiltered reconciliation would let a newer test entry demote a real
    production entry to `is_active=false` — corrupting the flag
    `resolve_role_entry_id` and the matching engine both read.
  - The webhook route ignores deliveries entirely in test scope, and now
    validates `workspace_id`, which was already parsed and thrown away.
  - The nightly full resync refuses to start in test scope rather than
    overwriting the dev sandbox, and moved from the dev environment to prod.
  - `/find-match` needed no change: `matching_engine` never calls Attio.

### Removed

- `infrastructure/crm-sync/scripts/dev-attio/` (~6.5k lines) and
  `server/scripts/postgres-sync/dev/`. The dev database is no longer synced
  from Attio at all — it is a sandbox that developers fill with `/add-*`.
  A fresh dev database is therefore empty, and `/find-match` has nothing to
  match against until someone creates buyer roles by hand; that is by
  design. `rds-tunnel-runbook.md` moved up out of `dev/` (prod's README
  links to it) and now covers both environments.
- The legacy standard `deals` object is out of the webhook's scope. It has
  **no `is_test` attribute**, so its records could never be assigned to an
  environment — a hole straight through the new filter. The nightly prod
  sync already deleted any row it produced, since that only fetches `deal`.
  The `deals` *PostgreSQL table* is unrelated and unchanged.
- `ATTIO_DEAL_OBJECT_SLUG`, and the per-workspace attribute-slug fallbacks
  in every params-mapper. Each first branch was verified absent from
  SOURCE's live attribute lists before deletion, enumerating each object in
  full rather than keyword-searching — a fuzzy query for "role title"
  returned only `job_title` and would have led to deleting `person.role`,
  which is live and stayed.
- `build_note_writer()`'s availability gate, which made note pushes silently
  optional. `ATTIO_NOTE_OBJECT_SLUG` is a constant now, so
  **`ATTIO_API_KEY` is effectively required for the `meetings` module** —
  safe today because the toolkit deploys one app in one container whose
  `ddl_commands` settings already require it.

### Fixed

- `source-attio/config/target-schema.json` said `person.postgres_table` was
  `"people"`; the model is `"person"`. The retired `dev-attio` copy had it
  right, so it was corrected before that directory was deleted.

## 2026-09-07

### Added

- Lead-magnet schema across SOURCE Attio and PostgreSQL, so the four tools
  (Valuation, M&A Readiness, GCC SME Benchmark, Buyer Network) have a real
  destination for what they compute. Until now those fields were written
  only to the legacy `lead_magnet_inbound*` Attio lists, which the Postgres
  mirror does not read — none of it reached the database.
  - 26 attributes on the `seller_role` list and matching `seller_roles`
    columns: benchmark score/band/quartile, nine `pct_*` percentile
    rankings, `implied_ev_low`/`_high`, `ebitda_adjusted`, `headcount`,
    `days_to_get_paid`, `data_consent`, the routing and dataset-governance
    fields, and `recommended_referral`.
  - The nine percentiles are discrete columns, not one JSONB blob, so each
    stays filterable — the reason they are real columns rather than
    `raw_attio`, which the nightly resync overwrites wholesale.
- `is_test` (checkbox) on all six Attio entities — `organizations`,
  `person`, `deal`, `note`, `seller_role`, `buyer_role`. One SOURCE
  workspace now serves both environments: `true` is dev/test, `false` is
  production. **Attio-only, with no PostgreSQL column** — the split is a
  read-side filter at sync time. Every write path sets it explicitly.
  (Corrected 2026-09-07: this entry originally said an unset record "matches
  neither filter and disappears from both environments". That is true of
  Attio's UI filter chips but **not** of the REST API, where `is_test eq
  false` does match records with no value — verified against a real record.
  It is why the sync can skip only an explicit `true` and does not depend on
  a stamping run having happened.)
- `tool_runs` table (`tool_run.py`, Postgres-only) and
  `activities.tool_run_id`. Complements `activities` rather than replacing
  it. Every subject reference is nullable with no CHECK requiring one —
  `activities_subject_present` makes it impossible to record a submission
  that failed before its Attio write, which is the lead-loss case the
  ledger exists to catch.
- Missing picklist options: `seller_role.readiness_band` (Early,
  Developing, Sale Ready, Market Ready), `buyer_role.target_geography`
  (Egypt, Global), `organizations.type` (Search Fund, HNWI).

### Fixed

- `seller_role.readiness_band` shipped as a select with **zero options**, so
  every write to it failed outright. Any readiness band written before now
  was silently lost.
- `server/scripts/postgres-sync/dev/sync-postgres.ps1` declared 31
  `seller_roles` columns against 30 `%s` placeholders — that insert could
  never have executed. Pre-existing and unrelated to the work above, but it
  sat in the block being edited.

### Notes

- Schema only: the tools are **not** repointed. `dopamine-relay` and
  `wusool-benchmark` are untouched, so Valuation and Readiness still run
  `toAed()` and write AED into USD-declared attributes. Deleting that
  conversion belongs with the repointing work.
- Alembic `f7a2c9e14b83`, revises `2565f7950641`.

## 2026-09-06

### Added

- `GET /desktop/verify` on the `meetings` module's desktop API surface, so
  the WusoolScribe desktop app's Scribe Push settings tab can check a
  server URL + API key against the backend before saving them, instead of
  only surfacing a bad config the next time the user pushes a meeting.
  Reuses the existing `require_desktop_api_key` dependency — the route
  body just confirms the Bearer token was accepted. New
  `verify_push_config` Tauri command in the desktop app calls it and
  blocks `set_push_config` from persisting on a rejected key or
  unreachable server.
- WusoolScribe desktop app: the "Summarize meeting" dialog now auto-polls
  `GET /desktop/meetings/{id}` every second after a push instead of
  requiring a manual "Check" click, stopping once the summary arrives. An
  in-flight guard keeps a slow response from ever piling up overlapping
  requests, and background-poll failures are silenced (a manual click
  still surfaces one) so a transient error doesn't spam a toast every
  second.

### Fixed

- WusoolScribe desktop app: Scribe Push save failures now show a short,
  non-technical toast ("Could not reach the server. Check the URL and your
  connection.") with no endpoint hostname or raw reqwest/DNS chain; the full
  error goes to the log instead of the UI.
- WusoolScribe 0.4.7: bundle Sonner's base stylesheet explicitly so Settings
  feedback remains visible in packaged builds. Successful Scribe Push saves
  now show one "Push destination saved" toast after verification and persistence.
- WusoolScribe desktop app: `ScrollArea` viewports now inherit the Root's
  max-height, so scroll surfaces bounded only by `max-h-*` (language picker,
  company autocomplete, release notes, pushed summary, chunk progress, and the
  Ollama model lists) scroll instead of silently clipping their overflow.
  Sticky transcript headers keep Radix's content wrapper as `display: block`.
- WusoolScribe desktop app: standardized application scroll surfaces on the
  shared shadcn/Radix `ScrollArea`, including the transcript viewport, dialogs,
  settings, onboarding, and pickers, so the scrollbar thumb follows light and
  dark themes consistently.
- WusoolScribe desktop app: removed redundant in-page Back buttons from the
  Settings and folder pages; navigation remains available through the sidebar.
- `meetings` module: the pushed meeting's `occurred_at` was computed
  server-side as `now() - duration_seconds`, which is wrong whenever a
  push happens well after the meeting itself (e.g. the next day) — the
  desktop app now computes and sends the actual `occurred_at` itself
  (derived from the local recording's saved timestamp minus its
  duration), and the server uses that value verbatim instead of guessing
  from its own clock.
- WusoolScribe desktop app: a meeting folder's list (and the main
  sidebar) relied implicitly on the SQLite query's `ORDER BY created_at
  DESC` surviving unchanged through every consumer with no sort of its
  own; now explicitly sorted latest-first once, at the single shared
  source (`SidebarProvider.fetchMeetings`), so it can't silently break if
  that array is ever touched elsewhere.
- WusoolScribe desktop app: the native macOS title bar and the sidebar's
  scrollbar both stayed in light mode regardless of the app's own
  dark-mode toggle. `tauri.conf.json`'s window `theme` only set the
  chrome once at launch, so it never followed later toggles — now synced
  via the Tauri window API on every theme change. The scrollbar's
  `::-webkit-scrollbar` CSS was silently ignored (WKWebView/Safari
  doesn't reliably support it) — switched to the shadcn `ScrollArea`
  (Radix, DOM-drawn), which isn't subject to that WebKit limitation.
- WusoolScribe desktop app: the tray/menu-bar icon reused the app's
  window icon instead of the dedicated `tray-icon.png`; the About
  dialog's logo now has rounded corners.

## 2026-09-05

### Added

- New `meetings` module: ingests transcripts pushed by the WusoolScribe
  desktop app, summarizes them via AWS Bedrock (forced-tool-call Converse,
  its own 300s-timeout client — a system-prompt capability
  `matching_engine`'s shared Bedrock client doesn't have), and writes the
  existing `meetings`/`notes` tables, optionally pushing the note to Attio
  when `ATTIO_NOTE_OBJECT_SLUG` is set. Async POST-then-poll contract
  preserved so the desktop app's Rust client is unchanged; runs as a
  `BackgroundTask` in the existing toolkit process — no SQS, no worker
  containers. This replaces Scribe's entire server-side summarization
  pipeline; the desktop app's own recording/local transcription is
  unaffected and out of scope, as is Slack delivery. `meetings` gains 5
  additive columns (`status`, `install_id`, `local_recording_id`,
  `summary_json`, `summary_started_at`) via one migration; this repo is now
  the writer of that table (previously Scribe, via the `scribe_pub` role —
  see `docs/dev/SCRIBE_INFRA_CONTRACT.md`, decommissioning that role and
  Scribe's EC2/SQS infrastructure is a separate follow-up). Prod's toolkit
  Terraform now enables Bedrock access (`enable_bedrock = true` +
  `bedrock_models`), previously dev-only.
- WusoolScribe desktop app: enabled the in-app auto-updater end to end. New
  `stacks/scribe-updates` Terraform stack (S3 + CloudFront, no custom domain
  yet) hosts a per-channel `latest.json` manifest and signed macOS
  `.app.tar.gz` payloads, published by a new manual-dispatch-only
  `scribe-release.yml` workflow restricted to a `scribe-release` GitHub
  Environment (**create it by hand, no protection rules needed, before the
  first run — the release role is unassumable without it**; the environment
  is purely an OIDC-trust label, `workflow_dispatch` itself is the human
  gate). The Tauri updater plugin, previously unregistered because its only
  configured feed was upstream Meetily's GitHub releases, now points at this
  feed; several dead/duplicate update-check code paths in the frontend were
  also fixed. Builds stay ad-hoc signed, unnotarized (no Apple Developer
  account) — accepted tradeoff is that macOS TCC will likely revoke and
  re-prompt for microphone/screen-recording access after most updates, since
  ad-hoc signing has no stable Team Identifier for TCC to key the grant on;
  Gatekeeper's quarantine prompt is unaffected either way, since the updater
  never downloads through a quarantine-setting API. macOS aarch64 only in
  this pass. See `docs/dev/SCRIBE_UPDATE_FEED.md`.

### Fixed

- `meetings` module: avoided a `MissingGreenlet` error by no longer
  re-reading a column that was just assigned via `func.now()` on an ORM
  instance under `AsyncSession` — assigning a server-side SQL expression
  leaves the attribute "expired" post-flush, and a later read
  (`to_meeting_record`) triggered an implicit async refresh that isn't
  safe there.
- `meetings` module: the desktop push's session is now committed before
  scheduling the summarization `BackgroundTask`, not after — this FastAPI
  version runs `BackgroundTasks` before a yield-dependency's own
  post-commit cleanup, so the background task's independent session
  couldn't see the just-created row yet, and every push was failing
  summarization with "meeting not found".
- WusoolScribe desktop app: release workflow's `pnpm` pinned to v10 to
  match the lockfile, and the updater tarball filename corrected — both
  were silently breaking `scribe-release.yml`'s ability to produce a
  working auto-update artifact.
- WusoolScribe desktop app: the main window now explicitly focuses on
  relaunch after an update — a relaunch via the updater spawns the new
  process without the Launch Services activation a normal double-click
  gets, so it was silently landing in the background with no way to
  bring it forward. The update toast was restyled onto sonner's native
  title/description/action API (fixing a doubled icon and cramped
  layout), and `scribe-release.yml` gained a `release_notes` input wired
  into both the GitHub release body and `latest.json`'s `notes` field —
  previously nothing set that field, so the in-app changelog dialog
  always showed an empty body.
- WusoolScribe desktop app: the sidebar footer's version was a hardcoded
  `"v0.4.0"` literal, never updated across three released versions —
  now reads the real `getVersion()`, matching how the About dialog
  already did it. Removed stale "delivered to Slack" copy from the push
  destination description (the meetings-module rewrite above already
  dropped Slack delivery from this pipeline). Fixed the recording-controls
  button and processing/saving overlays flashing right-of-center for one
  frame when navigating back to Home — both used a JS-computed
  `marginLeft` guess to fake centering against the sidebar's width
  instead of `position: absolute` inside the content row that already
  excludes it.

## 2026-09-04

### Fixed

- `sector_focus` and `target_geography` are multi-select enums in Attio but
  were rendered as free-text comma-separated boxes in the `/add-*` and
  `/edit-*` Slack forms. A typo ("Fin tech" for "Fintech") only surfaced as
  an `OptionNotFoundError` after `ack()`, by which point the modal had closed
  and everything else the operator had entered was discarded. Both now carry
  their option lists like every other select field and render as real
  multi-selects, so the invalid value can no longer be entered. Both are also
  covered by the live Attio drift check now, and the Slack view-limit test
  covers the four add/edit form builders (`sector_focus` sits at 85 of
  Slack's 100-option cap, previously unguarded).

## 2026-09-03

### Fixed

- Duplicate active buyer/seller role rows on concurrent `/add-buyer` /
  `/add-seller` for the same organization. Migration `b8f4c1e93a56` moved
  `UNIQUE` from `org_attio_id` to `legacy_entry_id` on the role tables, which
  left the create path's "does this org already have an active role" check
  unbacked by any constraint — two submissions could both pass it before
  either committed. `CreateBuyerUseCase`/`CreateSellerUseCase` now take a
  `SELECT ... FOR UPDATE` row lock on the parent organization
  (`OrganizationRepository.lock`) before that check, serializing same-org
  submissions.

### Changed

- Repo restructured into one `server/` modular-monolith project (#91):
  `terraform/` → `infrastructure/terraform/`,
  `workflows/{n8n,crm-sync,bedrock-ai}/` → `infrastructure/`, and
  `workflows/wusool-toolkit/` + `database/` merged into `server/` (no uv
  workspace, no path dependencies). Per-module and cross-module architecture
  fitness tests now enforce the layering rules. CI/CD path filters, Docker
  build context, and the migration path were repointed accordingly.

## 2026-09-02

### Fixed

- Nightly Attio → PostgreSQL resync hardened: SSM-online preflight,
  CloudWatch log streaming, a 20-minute execution deadline with timed-out
  command cancellation, and a memory/CPU-bounded singleton remote run so a
  runaway resync can't take the toolkit host offline.

### Removed

- Automatic `prod` → `dev` back-merge workflow.

## 2026-08-31

### Added

- `prod-postgres-sync` batch scripts for bulk SOURCE → prod data sync (#81).
- `seller_roles` lead-magnet fields exposed to the bot (#71).

### Fixed

- `/find-match` workflow correctness hardening (#85).
- Firecrawl web fallback restricted to Google Maps leads; Firecrawl markdown
  headings normalized (#84).
- SOURCE Attio field-slug mismatches for organization / person / seller role
  and deal name/stage/owner (#71, #78, #79); Attio-write registries corrected.

## 2026-08-30

### Changed

- `people` table renamed to `person` for singular-noun consistency (#73),
  with follow-up fixes to live webhook / nightly-resync SQL (#74).

## 2026-08-29

### Added

- SOURCE-Attio notes pipeline (#68).

### Changed

- Nightly Attio full-resync rewritten — removed N+1 queries, batched writes,
  added end-of-run consistency verification (#67).

### Fixed

- `/add-*` / `/edit-*` field mapping aligned with the current Postgres schema
  (#70).

## 2026-08-26

### Changed

- Buyer / seller / deal currency converted from AED to USD; seller
  lead-magnet fields added.

### Fixed

- Person soft-deleted on Attio `record.deleted` (#65).

## 2026-08-18

### Added

- Alembic + SQLAlchemy migrations established as the schema source of truth,
  applied in CD via SSM against each environment's RDS; a CI `alembic-check`
  job catches model/migration drift on every PR (#45).
- Real-time Attio → PostgreSQL sync via `POST /webhooks/attio` (upserts
  within ~1 second of an Attio change), plus a nightly automated full resync
  and automatic webhook pause/resume around bulk migrations (#47, #49, #50).

## 2026-08-16

### Added

- Continuous deployment: merging to `dev` / `prod` applies the changed
  OpenTofu stacks in dependency order (`base` → `n8n` / `toolkit` →
  `postgres`) and health-checks n8n and the toolkit bot before declaring
  success. Authentication is GitHub OIDC role assumption — no static AWS keys.
- `prod` as a real deployed environment: its own VPC, n8n instance, and RDS
  instance seeded from a dev snapshot (credentials rotated afterward).

### Changed

- Two hand-maintained Terraform environment directories consolidated into
  per-service stacks parameterized by `envs/{dev,prod}.tfvars`.
- Standardized on OpenTofu, version-pinned via
  `infrastructure/terraform/.opentofu-version`.

## 2026-08 (earlier)

### Added

- AWS Bedrock model access provisioned via Terraform for the matching
  engine — Claude Haiku 4.5, Claude Sonnet 4.6, and Qwen3-235B in
  `eu-central-1`.
- n8n password-reset / invite email on dev and prod, via AWS SES
  (`eu-central-1`, sandbox mode).
- Scribe integration groundwork: the `meetings` table, a least-privilege
  `scribe_pub` role on `wusool_crm`, and dev ↔ prod VPC peering so scribe
  can reach `wusool-prod-postgres`.
