# November 2026: Platform, data, and documentation

Delivery period: 15 October – 17 November 2026.

## Interactions engine (new)

The engine keeps relationship fields in Attio current from the team's
email and calendar.

- **Reads metadata only.** It reads each team mailbox's Gmail and Calendar
  for the last 12 months. It stores headers, subjects, and event details,
  never message bodies.
- **Live in production.** It filled in about 4,200 records on 16 November.
  Elsewhere it stays off.
- **Fields it keeps current.** Last and next interaction, last subject, last
  owner, and connection strength on Organizations and People. The numeric
  score behind each strength is kept in the database only.
- **Deals too.** Since 17 November, each Deal shows the same fields, taken
  from its buyer and seller together.
- **Calibrated before it wrote.** For a shadow week it only compared its
  strength with Attio's own. A company with no interactions counts as Very
  weak.
- **Careful writes.** It sends only changed values, and slowly. A field that
  should be empty, such as a passed "next interaction", is emptied. A
  strength with no recent interactions drops to Very weak.
- **New contacts from email.** It creates a Person and an Organization for
  new senders and tags them "Email sync". A new Person with no display name
  is named from the address. It adds up to 20 Persons a round.
- **Shared addresses go to review.** Shared mailboxes and domains are held
  in a review list. New cases are posted to Slack daily. Support-style
  senders are skipped.
- **Attio Companies and People are left alone.** The engine no longer
  updates them. Organizations and Person carry the new fields.
- **Gone records don't alarm.** A record deleted or merged away in Attio is
  logged and skipped, so it no longer keeps the sync alarm on.

## CRM data and sync

- **New deal stages.** All deals moved to 10 stages plus a status. See the
  [Toolkit page](november-2026-toolkit.md).
- **People carry a lead source,** like organizations. A new "Email sync"
  value marks records the engine created.
- **Interaction fields in the database.** Organizations, People, and Deals
  mirror the new Attio fields through the webhook and nightly sync.
- **Benchmark data in the database.** Benchmark scoring reads the peer
  dataset from the database. If it can't be read, scoring falls back to the
  original data. Scores don't change.
- **Reliable nightly sync.** A missing Toolkit instance now fails the run
  and alerts. A new alarm fires when no run has succeeded for 30 hours. The
  job uses its own narrow AWS role.
- **Safer deploys.** A deploy that finds the server mid-replacement now
  fails instead of reporting success without migrating.

## Detected and fixed

On 3 November, one download of the 70-page padel report starved the Toolkit
for about an hour. Nothing restarted it or paged anyone. A report's PDF is
now printed once, when it is published, and stored in Sanity. The download
button sends the reader to that file. Reports published earlier needed a
one-off backfill.

A host watchdog now checks the server every 30 seconds. After three misses
it restarts the stack. After about five minutes of failures it reboots the
host. The Toolkit has a memory cap, and a stuck browser is stopped after 10
seconds. Two new alarms report watchdog recoveries and a silent app log.

## Infrastructure and operations

- **Secrets load at startup.** The Toolkit reads its secrets from AWS
  Secrets Manager when it starts. Servers no longer keep a secrets file, and
  a secret edit takes effect on restart.
- **A safer database login.** The Toolkit's login can read and change data
  but not the schema. Schema changes use a separate admin login that only the
  deploy pipeline and admins can use.
- **n8n retired.** Both n8n servers are removed from the infrastructure.
- **Engine hosting.** The Engine runs on Cloudflare, behind email sign-in
  for staff, with a test copy and a live copy.
- **One audit trail.** AWS CloudTrail now records each event once instead
  of twice, saving about $20 a month.
- **Bulk templates bucket.** A public bucket holds only the two upload
  templates.
- **Faster website loads.** The Webflow embed script loads asynchronously,
  so a Toolkit outage can't slow the site.
- **Documentation checks.** CI now lints every page a branch changes, so a
  page that grows too long fails the pull request.

## Documentation

- **New pages.** The Technical section gained pages for the Engine, the
  MCP, benchmark editing, bulk upload, and find-match on the web. It also
  covers Scribe notes, speakers, and summaries. Lead-tool analytics and the
  interactions engine have pages too.
- **Runbooks and diagrams.** A Google access runbook covers setup, rotation,
  and revocation. Several Toolkit diagrams were redrawn, and the
  architecture diagram now shows Google Workspace and PostHog.
- **Frontend guidance.** The repository now has frontend guidelines for
  consistent web interfaces.
- **Release the Engine.** The deployment guide explains how the live Engine
  is brought up and rolled back.
