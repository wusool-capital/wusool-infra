# September 2026

Delivery period: Aug 12 – Sep 12, 2026.

## Cost impact

- Bringing meeting summarization in-house retired the external Scribe backend.
  This **saves approximately $100 per month** in compute costs.

## Wusool Toolkit (Slack bot)

- Built the matching engine end-to-end: buyer/seller scoring, AI-assisted
  reasoning via Bedrock, and Slack-based approvals, from scratch.
- Added `/edit-seller`, `/edit-buyer`, `/add-seller`, and `/add-buyer` for
  creating and updating buyer/seller profiles from Slack, writing to Attio
  and then the database. Role deletion is not supported from Slack.
- Added `/enrich-seller` / `/enrich-buyer` — researches a company from
  public sources and proposes values for empty fields, for review before
  saving.
- Added a Google Maps-backed seller discovery flow ("Find more sellers")
  for buyers with no strong existing matches.
- Merged the matching engine and the edit/add bot into one Slack bot
  (`Wusool Toolkit`) with `/toolkit-status` and `/toolkit-help`.
- Hardened match reasoning: fixed hard/soft requirement handling, JSON
  recovery from messy LLM output, and fallback-threshold scoring.

## Live-test fixes (this period's final week)

- Fixed a response-parsing bug that made the enrichment and lead-tool
  Firecrawl clients discard every search result.
- Fixed low-quality Google Maps search queries and unresolved "View on
  Maps" links found during live testing.
- Fixed Slack messages rendering literal asterisks instead of bold for
  bare-domain and multi-line values.
- Replaced a stale per-candidate "Enrich" button with a consistent
  `/enrich-*` hint line across match results and seller-add confirmations.
- Added missing success-path logging to Google Maps discovery, closing an
  observability gap that made a live bug undiagnosable.

## WusoolScribe (desktop meeting assistant)

- Shipped the desktop app's auto-updater with its own S3/CloudFront
  release feed and a versioning/release process.
- Added push-based meeting summarization in this repository, replacing the old
  hosted Scribe backend and saving approximately $100 per month.
- Fixed release-process, theming, and push-reliability bugs found during update
  rollout. These included lockfile, version display, native-theme permission,
  timestamp, and scrolling issues.

## Lead Magnets

- Migrated all four lead-magnet tools off Vercel/Render/Tally onto AWS.
- Fixed embed height, PDF export, and the valuation gate; logged an
  activity row in Attio after every lead-magnet write.
- Fixed repeat-submission and valuation data gaps found during end-to-end
  testing. Production cutover remains subject to the checks in
  [Delivery status](../operations/delivery-status.md).

### Before and after

| Area | Before | New platform |
| --- | --- | --- |
| Hosting | Vercel, Render, and Tally | One container on the existing AWS Toolkit instance |
| Region | Ohio, USA | Frankfurt, Germany |
| AI access | Anthropic API key exposed through the browser path | Bedrock through the instance role; no provider key in the browser |
| Lead safety | Readiness lost the submission when AI failed | A durable run is recorded before AI or Attio work |
| Database | Tool records did not reach Postgres | Attio writes are mirrored into Postgres |
| Deployment | Separate pages, backends, and provider-specific releases | One service, loaded into Webflow through `embed.js` |
| External hosting | Approximately $14 per month | Removed; the tools use shared AWS capacity |

### Benefits

- The submission ledger protects a lead before any AI or CRM call can fail.
  Idempotency handles network replays, while a sweeper resumes unfinished runs.
- Bedrock uses the EC2 instance role, removing AI provider keys and instructions
  from the browser.
- Attio remains the team's working system, while its webhook mirrors tool data
  into Postgres.
- Valuation and Benchmark retain deterministic results when optional AI fails.
  Buyer Network accepts applications without waiting for AI qualification.
- After the initial Webflow paste, `embed.js` controls tool addresses, sizing,
  cutover, and rollback without another page edit.

### Trade-offs

- The lead tools share compute with the Slack bot. An outage, restart, or
  resource bottleneck can affect both products, so production uses a larger
  instance.
- Readiness still requires Bedrock to produce its score and report. A failed AI
  call preserves the lead but cannot provide a fallback result.
- Firecrawl becomes a separate dependency and cost for comparable-company
  research, which Bedrock does not provide itself.
- Initial cutover still requires coordinated DNS, Secrets Manager, and Webflow
  changes. Buyer Network must replace Tally without both writing simultaneously.
- Migrating historical records from the old Attio lists was outside this work.
  Buyer Network and final Valuation still required recorded production checks
  at the end of the delivery period.

## CRM / Data model

- Added lead-magnet fields, `notes.primary_role`, and `organizations.region`
  to both Attio and Postgres.
- Retired the legacy Mandates concept in favor of Deal, and cleaned up
  redundant/dead organization fields.
- Converted buyer/seller/deal currency fields from AED to USD.
- Renamed the `people` table to `person` for naming consistency, and
  fixed the resulting webhook/nightly-sync fallout.
- Rewrote the nightly Attio full-resync to fix N+1 queries and batch
  writes.
- Fixed several rounds of field-slug mismatches between Postgres and the
  live Attio schema, surfaced by production traffic.

## Infrastructure

- Restructured Terraform into a stacks/modules layout with OIDC-based CD
  and digest-pinned ECR deploys.
- Put Wusool Toolkit in an Auto Scaling Group with a reachability
  alarm routed to Slack via AWS Chatbot.
- Migrated schema changes onto Alembic, wired into the deploy pipeline.

## Documentation

- Restructured the docs into a client-facing GitBook, with worked
  example walkthroughs added to every Slack command's user guide page.
