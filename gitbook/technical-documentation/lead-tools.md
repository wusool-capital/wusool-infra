# Website lead tools

The `lead_magnets` module serves the public tools on wusoolcapital.com and the
gated reports behind `/reports`. It runs in the shared Toolkit server, on a
second hostname pointing at the same container. The sub-pages cover each tool.

| Tool | Result for the visitor | AI | Page |
| --- | --- | --- | --- |
| Valuation | A low, mid, and high valuation from four blended methods | Enriches the report; the valuation itself is deterministic | [Valuation](lead-tools-valuation.md) |
| M&A Readiness | A 0–100 score, band, and recommendations | Required; there is no non-AI score | [M&A Readiness](lead-tools-readiness.md) |
| GCC SME Benchmark | Peer percentiles, a score, and an implied enterprise value | None | [GCC SME Benchmark](lead-tools-benchmark.md) |
| Buyer Network | Confirmation of the application | Optional internal note; never blocks | [Buyer Network](lead-tools-buyer-network.md) |
| Get Started | Confirmation of the seller enquiry | None | [Get Started](lead-tools-get-started.md) |
| Gated reports | The full report and a PDF, after an emailed code | None | [Gated reports](lead-tools-reports.md) |

Reports and Insights articles are published from Sanity; see
[Sanity and Webflow publishing](lead-tools-publishing.md).

## Embedding

Each tool page on wusoolcapital.com loads `embed.js`, which creates an iframe
and resizes it to fit. Adding `data-modal` and a `data-trigger` selector opens
the tool in an overlay instead; Get Started uses this to replace an old Tally
popup. Static pages are served under `/valuation/`, `/readiness/`,
`/benchmark/`, `/buyers/`, `/get-started/`, and `/report/`.

The tools hostname must stay DNS-only in Cloudflare, so edge caching never
delays an `embed.js` deploy or rollback.

## The write contract

Every tool that records a lead follows the same order, which makes losing a
lead impossible:

![The lead write contract](../.gitbook/assets/lead-write-contract.svg)

1. **Record the submission** as a `tool_runs` row, committed before anything
   else happens.
2. **Respond** to the browser. Nothing that fails after this loses the lead.
3. **AI work**, where the tool has any. Valuation and Benchmark fall back to
   their own calculations; Readiness has no fallback by decision.
4. **Write to Attio**, always with the test flag set: the organization, a
   seller or buyer role, the person, and a deal at stage Inbound.
5. **Email the visitor** a confirmation through Amazon SES, with a Book a
   Call link.
6. **Email the team** a notice linking to the Attio organization and deal.
7. **Finish** the run and add its activity.

A sweeper resumes any run left unfinished. The two emails are tracked as
separate stages, so a resume never re-sends the visitor's confirmation. An
email step with no address configured is skipped for good rather than
retried; the lead is already in Attio.

The database is never written directly for CRM data: Attio's webhook mirror
copies the records across.

## Duplicates

`tool_runs` is an append-only log: every genuine attempt gets its own row.
An exact network retry of the same request (same submission ID) reuses its
row instead of rerunning the pipeline. The CRM is where duplicates are
merged:

- **Organization:** matched by domain and name, then updated with the
  latest values.
- **Person:** matched by email. A match only gets blank fields filled; a
  name is never overwritten.
- **Deal:** one per organization. A matched deal is left untouched, so a new
  lead never moves a Qualified deal back to Inbound.

## Rules that fail silently if broken

- **Send USD, convert nothing.** Every destination is USD; a wrong
  conversion is off by 3.67× with nothing in the data to show it.
- **Always set the test flag.** A record without it disappears from both the
  test and production views in Attio.
- **Attio first.** A nightly job overwrites the database from Attio.

## Endpoints

| Endpoint | Purpose |
| --- | --- |
| `POST /enrich`, `POST /analyze`, `POST /compare` | Valuation report building; stateless |
| `POST /submit-lead` | Records the valuation |
| `POST /readiness/score` | Records and scores a Readiness submission |
| `POST /benchmark` | Records and scores a Benchmark submission |
| `POST /buyer/apply` | Records a Buyer Network application |
| `POST /get-started` | Records a Get Started enquiry |
| `GET /reports/{slug}`, `POST /reports/{slug}/unlock`, `POST /reports/{slug}/unlock/verify`, `GET /reports/{slug}/pdf` | Gated reports |
| `POST /reports/webhooks/sanity` | Sanity publish webhook |

Common responses: `422` for invalid input and `429` for rate limiting. A
repeat submission is never rejected; it is recorded as a new attempt.

## Failures and alerts

- Attio and stale-run failures are retried by the sweeper.
- An email that permanently fails to send raises a CloudWatch alarm on the
  Toolkit instance's log group. It uses the same alert topic as the other
  Toolkit alarms.

## Code

`server/app/modules/lead_magnets` and its README; the tool pages are in its
`static` folder, with their own README. Alarms are defined in
`infrastructure/terraform/modules/toolkit-ec2`.
