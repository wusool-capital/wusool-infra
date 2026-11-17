# Delivery status and open items

_Last updated: 17 November 2026._

This register separates what the repository delivers from what has been
verified live. Update it at each handover or significant release.

## Delivered

| Capability | Status |
| --- | --- |
| Development and production AWS environments | Delivered; confirm live state |
| Branch-based deploys with migrations and health checks | Delivered |
| Toolkit in Slack: matching, `/check-buyer`, add, edit, enrich | Delivered; production instance enabled |
| Discrepancy check in the pre-match popup | Delivered |
| Approving a match creates a Qualified deal in Attio | Delivered |
| Seller discovery from Google Maps, with website verification | Delivered |
| One buyer role per vertical | Delivered |
| Deal pipeline with 10 stages and a separate status | Delivered; all 124 deals migrated |
| Bulk upload of buyers and sellers from Slack | Delivered |
| Find-match web app at `/app` | Delivered |
| Wusool MCP for Claude: find, add, edit, bulk import, benchmark editing | Delivered; confirm live sign-in |
| Wusool Engine at `engine.wusoolcapital.com`: Buyers and Sellers on live data | Delivered to production; other pages greyed out |
| PostgreSQL on private, encrypted RDS | Delivered; restore test outstanding |
| Attio real-time webhook and nightly resync, with soft deletes | Delivered; verify the webhook subscription and alert live |
| Interactions engine: Gmail and Calendar metadata into PostgreSQL | Live on production; off by default elsewhere |
| Interactions engine: create Persons and Organizations from email | Live on production since 16 Nov, up to 20 Persons a round |
| Interactions engine: roll interactions up to Deals | Live on production since 17 Nov |
| Interactions engine: Attio Companies and People | Left in place on purpose; the engine no longer updates them |
| Website lead tools: Valuation, Readiness, Benchmark, Buyer Network, Get Started | Delivered; see open items for end-to-end checks |
| Gated reports on `/reports`, with emailed code, PDF, and A4 sheet view | Delivered |
| Interactive reports and whole-page Insights articles | Delivered |
| Website analytics and session replay in PostHog, after consent | Delivered; confirm the project setting is on |
| Sanity Reports & Insights Studio, Webflow sync, home banner, Insights articles | Delivered; confirm webhooks live |
| WusoolScribe 0.8.7 for Apple-silicon Macs, with speaker names and meeting notes | Delivered; ad-hoc signed |
| Toolkit host watchdog, memory cap, and recovery alarms | Delivered; confirm alarms live |
| Monitoring: alarms, security findings, Slack and email routing | Delivered in code; confirm subscriptions live |

## Open items

| Priority | Item | Done when |
| --- | --- | --- |
| High | Assign primary and backup owners and document access and escalation | Ownership register complete |
| High | Agree recovery targets and test a PostgreSQL restore | Approved targets and a dated restore test |
| High | Verify the nightly resync failure alert end to end | A deliberate failure produces an acknowledged alert |
| High | Export the Sanity dataset on a schedule; reports have no other copy | A dated export and a tested import |
| High | Alert on abandoned lead-tool runs, report code email failures, and Sanity or Webflow sync failures | Alarms exist and have been tested |
| Medium | Send interactions review cases to the mailbox owner as a direct message, with a Dismiss button | Only the owner gets a case, and a dismissed case stays dismissed |
| Medium | Add RDS alarms; consider Multi-AZ | Alarms exist; decision recorded |
| Medium | Verify Buyer Network and Valuation submissions end to end against live Attio | Dated production test |
| Medium | Confirm the Sanity webhooks are enabled and signed, and that Webflow cards go live without a site publish | Dated check |
| Medium | Verify SES sender identities and sandbox status, and test every lead and code email | Dated delivery test |
| Medium | Make the Scribe beta channel reachable, or remove it | The app can read a beta feed, or the option is gone |
| Medium | Verify Scribe install, update, and CRM push on a client Mac | Dated test |
| Medium | Confirm People Data Labs responses against a live account | Recorded successful lookup |
| Medium | Run the notes identity backfill review on production data | Reviewed dry run |
| Medium | Write the postmortem for the 28 September buyer-role deactivation | Postmortem filed |
| Medium | Run the report PDF backfill for reports published before 5 November | Every older report's download works |
| Medium | Write the postmortem for the 3 November report PDF stall | Postmortem filed |
| Low | Keep the discovery daily cap across restarts | Cap survives a deploy |

## Sign-off rule

Don't describe an item as live from repository configuration alone. Mark it
verified only when an operator records the environment, date, evidence, and
result. A failed critical check stays open with an owner and target date.
