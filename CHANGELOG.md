# Changelog

Significant changes to the Wusool platform, newest first. This file records
product and operational milestones rather than individual implementation
details. Git history remains the source for commit-level changes.

The project has no version tags: merges to `dev` and `prod` deploy their
respective environments. See [Delivery status](docs/operations/delivery-status.md)
for current production evidence and open handover items.

## 2026-09-13

### Fixed

- Restored the nightly Attio full resync, which had failed every night from
  2026-09-03 to 2026-09-12 without alerting anyone. It located the Toolkit
  container by exact name, but Compose names that container with a project and
  index suffix, so the lookup matched nothing and each run aborted before doing
  any work. It is now found by its Compose service label.

### Added

- A failed nightly Attio resync now raises an alert on the environment alert
  topic instead of being visible only in the Actions tab.
- Added a Vale quality gate for the client GitBook, including terminology,
  readability, structure, and page-length rules.
- Added a contributor-facing documentation style guide.

### Changed

- Reorganized the GitBook around consolidated product guides, technical
  references, and operational handover runbooks.
- Added text-based, end-to-end examples with expected results and recovery
  guidance across every product guide.
- Added compact Mermaid flow diagrams for the Toolkit's matching, editing,
  adding, and enrichment workflows.
- Condensed the changelog into milestone summaries; commit-level detail remains
  available in Git history.

### Fixed

- Every embedded lead-magnet tool was cut off partway down the form with no
  way to scroll to the rest, losing any visitor who had not already finished.
  The embedded page measured its height from a value that, inside an iframe,
  can never report less than the iframe already was, so the iframe never grew
  past its placeholder; the loader then set `scrolling="no"`, which turned the
  clipped remainder into unreachable content rather than a scrollbar. Height
  is now measured from the page body, the embed carries no fixed dimensions at
  any screen size, and it clears the fixed height the marketing site puts on
  its embed containers.
- The four tools now use the marketing site's DM Sans rather than Inter and
  JetBrains Mono. The Valuation tool in particular was rendering in the
  browser's default serif with form fields overflowing their card: a stray
  `<style>` tag at the top of its stylesheet made the browser discard the rule
  carrying both its font and its box-sizing reset.
- The Valuation form's paired fields no longer stay side by side on a phone —
  inline styles were overriding the small-screen breakpoint.
- Corrected `/toolkit-status` to report the deployed development or production
  environment instead of falling back to `development` in production.
- Lead-magnet submissions (Valuation, M&A Readiness, GCC SME Benchmark, Buyer
  Network) now create or reuse an Attio person record for the visitor's
  email, so a lead lands attached to a CRM contact instead of only an
  organization. Benchmark submissions also now carry their raw financial
  figures, consent flag, and funding stage through to Attio, and M&A
  Readiness's country now reaches the organization record.
- The GCC SME Benchmark form's optional mobile number field was silently
  dropped before it ever reached the server — its own submit script never
  read the field into the request. Now carried through to the visitor's
  Attio person record.
- The Valuation tool's revenue and profit before tax at the visitor's
  last funding raise were computed client-side and shown back to the
  visitor, but never included in the lead submission. Now reaches
  `tool_runs.payload`.

## 2026-09-12

This release period is summarized in
[September 2026 deliverables](docs/deliverables/september-2026.md).

### Added

- Delivered Wusool Toolkit as one Slack application for matching, buyer and
  seller profile management, enrichment, discovery, status, and help.
- Added structured company-data enrichment through Diffbot and People Data
  Labs, with Firecrawl and Bedrock fallback research.
- Added WusoolScribe transcript submission, server-side summarization, Attio
  note creation, status synchronization, and signed desktop updates.
- Added Valuation, M&A Readiness, GCC SME Benchmark, and Buyer Network tools
  to the shared Toolkit backend.
- Added Auto Scaling Group recovery, external reachability monitoring, and
  Slack-routed infrastructure alerts for Toolkit.

### Changed

- Consolidated duplicated background-task, idempotency, organization lookup,
  Bedrock retry, and database utilities across server modules.
- Improved matching requirements, confidence reporting, geography handling,
  and public seller discovery.
- Converted profile country and region fields to controlled multi-selects
  while preserving unsupported stored values safely.
- Improved the Attio full-resync pipeline with batched reads and writes and
  end-of-run consistency validation.

### Fixed

- Corrected Firecrawl response parsing that discarded enrichment and
  lead-tool search results.
- Corrected Google Maps discovery queries and direct place links.
- Prevented unsupported multi-select values from being cleared during an
  unrelated profile edit.
- Fixed Slack formatting, enrichment review, provider-data validation, test
  isolation, and Scribe release and push reliability issues.

## 2026-09-08

### Added

- Introduced the client-facing GitBook with user, technical, handover, and
  WusoolScribe documentation.

## 2026-09-07

### Added

- Migrated the four website lead tools into the AWS-hosted backend with a
  durable submission ledger, idempotency, retry sweeper, and Attio writes.
- Added modular-monolith boundaries and architecture checks across the server.

### Changed

- Replaced legacy mandate terminology and fields with the Deal model.
- Standardized buyer, seller, and deal currency fields on USD.

## 2026-09-05

### Added

- Added the meetings module and moved WusoolScribe summarization into the
  Wusool backend, removing the separate hosted summarization dependency.

## 2026-08-31

### Changed

- Renamed the `people` table to `person` and aligned Attio webhook and nightly
  synchronization mappings with the live SOURCE workspace.

## 2026-08-18

### Added

- Established Alembic migrations as the PostgreSQL schema authority and added
  migration consistency checks to CI and deployment.
- Added signed Attio webhooks, nightly full synchronization, and automatic
  webhook pause and resume around bulk migrations.

## 2026-08-16

### Added

- Added branch-based continuous deployment using GitHub OIDC, immutable image
  digests, ordered OpenTofu applies, migrations, and health checks.
- Established separate development and production AWS environments with their
  own networks, n8n instances, databases, secrets, and deployment state.

### Changed

- Consolidated infrastructure into reusable OpenTofu stacks parameterized by
  environment configuration.

## 2026-08

### Added

- Provisioned AWS Bedrock model access for matching and summarization.
- Added n8n invitation and password-reset email through AWS SES.
- Added the initial WusoolScribe database and networking integration.
