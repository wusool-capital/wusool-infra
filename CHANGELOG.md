# Changelog

Meaningful changes to `wusool-infra` — infrastructure, the Wusool Toolkit
Slack bot, and the Attio ↔ PostgreSQL data platform.

The project has no version tags: every merge to `dev` / `prod` deploys.
Entries are grouped by date, newest first, using the
[Keep a Changelog](https://keepachangelog.com/) categories. For the current
delivered state and outstanding items see
[`docs/handover/README.md`](docs/handover/README.md).

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
