# Changelog

Significant changes to the Wusool platform, newest first. This file records
product and operational milestones rather than individual implementation
details. Git history remains the source for commit-level changes.

The project has no version tags: merges to `dev` and `prod` deploy their
respective environments. See [Delivery status](docs/operations/delivery-status.md)
for current production evidence and open handover items.

## 2026-09-18

### Added

- **Get Started** is now a selectable lead-magnet on an organization's
  `lead_source_detail`, alongside the Valuation Tool, M&A Readiness Tool,
  Buyer Form and GCC SME Benchmark. Like the Benchmark before it, the tool
  postdates the legacy workspace, so there is no historical data to backfill
  — it only needs somewhere for new leads to land.

## 2026-09-17

### Added

- The M&A Readiness Tool and Valuation Tool now unlock the full report a
  few seconds after the booking-CTA is clicked. The unlocked report can be
  saved as a PDF via browser print.
- The **Get Started** form now sends the same two SES emails the other four
  lead magnets do. A visitor gets a confirmation with a "Book a Call" link.
  The team gets an internal notice with the submitted figures and links back
  to the Attio organisation/deal. It had been left out of the email dispatch
  when that feature shipped, since Get Started didn't exist on `dev` yet.

### Changed

- The four lead magnets are Valuation Tool, M&A Readiness Tool, GCC SME
  Benchmark, and Buyer Form. None of them reject a repeat submission with
  `409 you have already completed this` any more.
- A visitor can resubmit any number of times, for any tool. Every
  genuinely new attempt gets its own permanent row and its own CRM
  activity entry. Nothing is ever lost or merged.
- Dedup at the organization/person level is unaffected. A repeat
  submission still updates the same Attio organization and person rather
  than creating a new one.
- An exact retried request — a network retry of the same submission, not
  a new visit — still reuses its original row instead of reprocessing.
  A visitor is never emailed twice, and the M&A Readiness Tool is never
  double-billed for its Bedrock call.

## 2026-09-16

### Added

- The four lead magnets (Valuation Tool, M&A Readiness Tool, GCC SME
  Benchmark, Buyer Form) now stamp `organizations.lead_source_detail`
  themselves, on every submission. The field existed since 2026-09-15, but
  nothing wrote it except the historical migration and manual Attio edits.
  If a company submits through more than one tool, the most recent tool
  wins — the same behavior as every other lead-magnet-supplied organization
  attribute.

### Fixed

- Organizations removed from Attio (soft-deleted, `removed_at` set) could
  still surface: a new lead-magnet submission could dedupe-match and reattach
  itself to a removed org's old record instead of creating a fresh one, and
  the matching engine's candidate pool for `/find-match` could still include
  sellers on a removed organization, or seller roles superseded by a newer
  submission (`is_active = false`). Also affected `/edit-seller`'s,
  `/edit-buyer`'s, and `/find-match`'s buyer-resolution org-name search,
  which already excluded superseded roles but not removed orgs. All four
  queries now exclude removed organizations.

## 2026-09-15

### Added

- Organizations now record **which lead-magnet a lead came in through** —
  Valuation Tool, M&A Readiness Tool, Buyer Form, or GCC SME Benchmark — in a
  new `lead_source_detail` field on both Attio and Postgres. The existing
  `lead_source` only ever said Inbound or Outbound, so "which leads came from
  the Valuation Tool?" could not be answered outside the legacy workspace.

  The tool name had never been lost in translation: the migration simply never
  read it, even though the mapping configuration had described carrying it
  across since the beginning. Where a company used two tools, the most recent
  one is recorded, and a genuinely ambiguous pair (identical timestamps) is
  reported rather than guessed at.

- Every lead-magnet submission (Valuation, M&A Readiness, GCC SME Benchmark,
  Buyer Network) now sends two emails via SES: a branded confirmation to the
  visitor with a "Book a Call" link, and an internal notice to the deal team
  with the submitted details and links back to the Attio organisation/deal.
  Both are tracked and retried independently, so a failed send never
  re-sends an email that already landed and never risks the lead itself —
  the Attio write is already durable by the time either email is attempted.
  A CloudWatch alarm now fires on the shared environment alert topic if a
  send permanently fails after SES's own retries are exhausted.

- A record deleted in Attio now disappears from Postgres for **all six**
  mirrored objects, not just two. Deals, notes, buyer roles and seller roles
  had no way to record a deletion at all: a deal deleted from the CRM stayed
  in Postgres indefinitely, so matching, reporting and Slack search kept
  counting and offering records nobody could see in Attio any more. The
  webhook now marks them removed within seconds, and a record re-created in
  Attio comes back live on its own.

  The removal is recoverable by design — rows are marked, never erased,
  because their Postgres-side children (deal-stage history, generated
  documents, match results) are computed here and could not be rebuilt from
  Attio. Deletion stays authored in Attio only; there is still no way to
  delete a record from Slack or from Postgres.

### Fixed

- A person deleted in Attio and then re-created in it came back invisible:
  the deletion marker was never cleared on re-appearance, so the row was
  present but skipped by everything that filters out deleted records.

- Seller discovery's geography restriction silently produced wrong results
  for a buyer whose `target_geography` includes a multi-country region:
  geocoding the bare string `"GCC-wide"` (or the raw `"GCC-wide, Global"`
  buyers actually carry) matched an unrelated US institution commonly
  abbreviated "GCC" with `status: OK` and no error, restricting the search
  to Glendale, CA instead of the Gulf states the buyer meant — traced live
  from a buyer with `target_geography: ["GCC-wide", "Global"]` returning
  only German sellers. Geocode results are now validated against Google's
  own place-type and partial-match signals before they're trusted, and
  `target_geography`'s known multi-country regions (GCC, MENA) and
  explicit no-restriction terms (Global, Worldwide) resolve from a fixed
  table instead of a single geocode call that can't answer them correctly.

## 2026-09-14

### Added

- WusoolScribe desktop app: a "Send feedback" bug icon in the sidebar opens
  a form (category, message, optional contact) that a new
  `POST /desktop/feedback` route on the `meetings` module durably records
  in a new `feedback_submissions` table and best-effort emails via AWS SES
  (`notifications` module) — no email credential ships in the desktop
  binary, and a submission is never lost even if SES delivery fails.
- Every lead-magnet submission now creates an Attio deal at stage
  **Inbound**, so a new lead lands in the pipeline instead of waiting to be
  keyed in by hand. One deal per organisation: a company that runs two tools
  is one lead, and a deal an advisor has already advanced is never dragged
  back to Inbound. Each deal is assigned to an advisor on creation, with a
  configured fallback so the write cannot silently stop if that advisor
  leaves the workspace.
- The site's **Get Started** form is now served by the platform instead of
  Tally, as the fifth lead-magnet tool. A submission records the lead before
  anything else can fail. It then writes the company, the contact, and the
  seller's own figures — revenue, EBITDA, years in business, and sell
  timeline — to the CRM. It embeds as a modal, so the existing button opens
  it in place and the page's URL never changes. The visitor now sees a
  confirmation instead of the form silently vanishing.

### Changed

- Replaced `discovery`'s Firecrawl Google Maps scrape with Google's Places
  API (New) and Geocoding API. Seller leads now carry a real place link
  (`googleMapsUri`) instead of one recovered by regex-matching scraped
  links, and a buyer's geography is enforced against each result's country
  rather than only appearing as words in the search query.

### Fixed

- Buyer requirement extraction now sees a buyer's `target_geography`,
  `ebitda_ceiling`, and several other already-structured `buyer_roles`/
  `organizations` fields that were silently dropped between the database
  row and the Bedrock prompt. A buyer with a real, populated
  `target_geography` (e.g. "GCC-wide, Global") could still trigger a fully
  unrestricted seller-discovery search, because nothing ever told the
  extraction step it existed — traced live from a UK-HQ'd buyer's search
  surfacing Frankfurt/Cologne results with no geography signal anywhere in
  the query. Also fixes a buyer with no free-text investment strategy/notes
  on file: the prompt used to show the literal placeholder `Unknown` for a
  blank field, which the model would sometimes echo back as if it were real
  buyer data (a search for "Unknown companies").
- A visitor who retried a lead-magnet form after a dropped network response
  was told they had already completed it. Each click generated a new
  submission id, so the retry looked like a second visit rather than the same
  one. The id is now fixed for the life of the page, which the Buyer Network
  and M&A Readiness forms could both hit.
- A stale lead-magnet submission stuck in the retry queue could abort the
  entire sweep instead of just itself. That could roll back every other lead
  the same pass had already finished. The write contract promises a failure
  "never" escapes the retry step. That wasn't quite true for the Buyer
  Network's target geography, which has been live since it shipped.

## 2026-09-13

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

- Restored the nightly Attio-to-PostgreSQL full resync, which had failed every
  night from 2026-09-03 to 2026-09-12. Production PostgreSQL relied on the
  real-time webhook alone for that period and should be reconciled against
  Attio.
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
