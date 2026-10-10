# September 2026

Delivery period: 12 August – 14 September 2026.

This period delivered the platform's foundations: the Slack bot, in-house
meeting summaries for WusoolScribe, and the CRM data model. The lead tools
also moved onto Wusool's own infrastructure.

## Cost impact

- Bringing meeting summaries in-house retired the external Scribe backend,
  **saving about $100 a month**.
- Moving the lead tools off Vercel, Render, and Tally removed about **$14 a
  month** of external hosting.

## Wusool Toolkit (Slack bot)

- **Matching engine, built from scratch.** Buyer and seller scoring,
  AI-written reasoning, and approvals in Slack.
- **Profile commands.** `/add-buyer`, `/add-seller`, `/edit-buyer`, and
  `/edit-seller` create and update profiles from Slack, writing to Attio
  first.
- **Research.** `/enrich-buyer` and `/enrich-seller` research public sources
  and propose values for empty fields, for review before saving.
- **Seller discovery.** "Find more sellers" searches Google Maps when no CRM
  seller fits. It moved onto Google's official Places API, so each lead has
  a real map link and is checked against the buyer's countries.
- **One bot.** Matching and profile editing merged into one Slack app,
  Wusool Toolkit, with `/toolkit-status` and `/toolkit-help`.
- **Fixes from live testing.** Research results were being discarded, map
  links didn't resolve, and Slack formatting showed stray asterisks. The AI
  also wasn't seeing a buyer's target geography. All were fixed.

## Website lead tools

- **Moved onto Wusool's platform.** All four tools (Valuation, M&A
  Readiness, GCC SME Benchmark, and Buyer Network) moved from Vercel, Render,
  and Tally onto AWS in Frankfurt.
- **Get Started launched** as the fifth tool, replacing the Tally form behind
  the site's main button. It records the seller's own figures in the CRM.
- **Every lead becomes a deal.** Each submission creates an Inbound deal in
  Attio, assigned to an advisor, so leads land in the pipeline without
  re-keying. A company using two tools is still one lead.
- **Every lead gets a contact.** Submissions create or reuse an Attio person
  for the visitor's email.
- **Embedding fixed.** Tools embedded on the site were cut off partway down
  the form. They now size themselves correctly on every screen and use the
  site's font.
- **Nothing is lost.** Each submission is recorded before any AI or CRM
  step, and a background job finishes anything interrupted.

### Before and after

| Area | Before | Now |
| --- | --- | --- |
| Hosting | Vercel, Render, and Tally | One service on Wusool's AWS |
| Region | Ohio, USA | Frankfurt, Germany |
| AI access | An AI provider key exposed to the browser | AI reached securely from the server |
| Lead safety | Readiness lost the lead when AI failed | Every lead is recorded first |
| Database | Tool records never reached the database | Attio is mirrored into the database |
| Website changes | Separate pages and backends to update | One script on the site controls every tool |

### Trade-offs

- The lead tools share a server with the Slack bot, so an outage affects
  both. Production uses a larger instance to compensate.
- Readiness still needs AI to produce a score. If AI fails, the lead is
  recorded but there's no result to show.
- Firecrawl is a separate paid dependency for finding comparable companies.

## WusoolScribe

- **Automatic updates** through Wusool's own release feed.
- **In-house summaries.** Pushed meetings are summarized on Wusool's server
  and filed in Attio, replacing the old hosted backend.
- **In-app feedback.** A bug icon sends feedback to the team; every
  submission is stored, so none are lost.
- Fixes to releases, theming, timestamps, and scrolling found during the
  first updates.

## CRM and data

- **Cleaner data model.** Lead-tool fields, meeting-note roles, and
  organization regions were added to Attio and the database. The old
  "Mandates" concept was replaced by Deals, and unused fields were removed.
- **USD everywhere.** Buyer, seller, and deal amounts were converted from AED
  to USD.
- **Faster nightly sync.** The nightly Attio sync was rewritten for speed. It
  had failed from 3 to 12 September; it was restored on 13 September and now
  alerts when it fails.

## Infrastructure

- **Automated deploys.** Infrastructure is organized into reviewable stacks,
  with secure deploys from GitHub and pinned application images.
- **Self-healing.** The Toolkit runs in an Auto Scaling Group, and a
  reachability alarm posts to Slack.
- **Safe schema changes.** Database changes go through reviewed migrations
  in the deploy pipeline.

## Documentation

- **This GitBook.** A client-facing GitBook with user guides, technical
  references, and handover runbooks, with worked examples on every page.
- **Quality checks.** An automated check enforces terminology, readability,
  and page length.
