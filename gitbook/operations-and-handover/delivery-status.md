# Delivery status and open items

_Last updated: 10 October 2026._

This register separates what the repository delivers from what has been
verified live. Update it at each handover or significant release.

## Delivered

| Capability | Status |
| --- | --- |
| Development and production AWS environments | Delivered; confirm live state |
| Branch-based deploys with migrations and health checks | Delivered |
| Toolkit in Slack: matching, `/check-buyer`, add, edit, enrich | Delivered; production instance enabled |
| Discrepancy check before every match | Delivered |
| Approving a match creates a Qualified deal in Attio | Delivered |
| Seller discovery from Google Maps, with website verification | Delivered |
| One buyer role per vertical | Delivered |
| PostgreSQL on private, encrypted RDS | Delivered; restore test outstanding |
| Attio real-time webhook and nightly resync, with soft deletes | Delivered; verify the webhook subscription and alert live |
| Website lead tools: Valuation, Readiness, Benchmark, Buyer Network, Get Started | Delivered; see open items for end-to-end checks |
| Gated reports on `/reports`, with emailed code, PDF, and A4 sheet view | Delivered |
| Sanity Reports Studio, Webflow sync, home banner, Insights articles | Delivered; confirm webhooks live |
| WusoolScribe 0.7.7 for Apple-silicon Macs | Delivered; ad-hoc signed |
| n8n in both environments, with pinned images, logs, and alarms | Delivered; no backup |
| Monitoring: alarms, security findings, Slack and email routing | Delivered in code; confirm subscriptions live |

## Open items

| Priority | Item | Done when |
| --- | --- | --- |
| High | Assign primary and backup owners and document access and escalation | Ownership register complete |
| High | Back up n8n data, then test a restore | A successful isolated restore |
| High | Agree recovery targets and test a PostgreSQL restore | Approved targets and a dated restore test |
| High | Verify the nightly resync failure alert end to end | A deliberate failure produces an acknowledged alert |
| High | Alert on abandoned lead-tool runs, report code email failures, and Sanity or Webflow sync failures | Alarms exist and have been tested |
| Medium | Add RDS alarms; consider Multi-AZ | Alarms exist; decision recorded |
| Medium | Verify Buyer Network and Valuation submissions end to end against live Attio | Dated production test |
| Medium | Confirm the Sanity webhooks are enabled and signed, and that Webflow cards go live without a site publish | Dated check |
| Medium | Verify SES sender identities and sandbox status, and test every lead and code email | Dated delivery test |
| Medium | Make the Scribe beta channel reachable, or remove it | The app can read a beta feed, or the option is gone |
| Medium | Verify Scribe install, update, and CRM push on a client Mac | Dated test |
| Medium | Confirm People Data Labs responses against a live account | Recorded successful lookup |
| Medium | Run the notes identity backfill review on production data | Reviewed dry run |
| Medium | Write the postmortem for the 28 September buyer-role deactivation | Postmortem filed |
| Low | Keep the discovery daily cap across restarts | Cap survives a deploy |
| Low | Bring the production n8n re-provisioning procedure in line with the module | Reviewed drill |

## Sign-off rule

Don't describe an item as live from repository configuration alone. Mark it
verified only when an operator records the environment, date, evidence, and
result. A failed critical check stays open with an owner and target date.
