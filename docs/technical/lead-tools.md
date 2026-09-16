# Website lead tools

## Purpose and delivery status

Four tools collect visitor details and provide an immediate business outcome:

| Tool | Result | AI behavior |
| --- | --- | --- |
| Valuation | Blended DCF, trading-comps, transaction-comps, and VC-method range | AI enriches the report; the valuation has deterministic fallbacks. |
| M&A Readiness | Score, band, and recommendations from 15 answers | Bedrock is required; there is no invented non-AI score. |
| GCC SME Benchmark | Peer percentiles, score, and implied enterprise value | Deterministic dataset calculation. |
| Buyer Network | Registers acquisition interest | Optional AI qualification never blocks the application. |

All tool pages and seven endpoints are implemented in the Toolkit runtime.
Benchmark and Readiness have been verified over HTTP with live dependencies.
Buyer Network and final valuation submission are built and tested. They remain
unverified in production until an end-to-end Attio/PostgreSQL check is recorded.

## Components and embedding

The `lead_magnets` module contains per-tool calculations, a shared submission
service, a `tool_runs` write-ahead ledger, Bedrock/Firecrawl/Attio providers,
API endpoints, and static pages. Caddy exposes the same Toolkit container at
the website-tools hostname. Each wusoolcapital.com tool page loads `embed.js`,
which creates and resizes an iframe.

## Data flow

Ledger-backed submissions follow this contract:

1. Validate the request and commit a `tool_runs` row before promising success.
2. Return the result when that tool's required calculation is available.
3. Complete non-blocking AI work where applicable.
4. Create/update the organization, seller/buyer entry, and person in Attio
   with an explicit `is_test` value. The person write is best-effort — a
   failure there does not fail the run, since the lead is already durable.
5. Email the visitor an HTML confirmation via SES, with a "Book a Call" link.
6. Email the internal team an HTML notice via SES, with the submitted details
   and links back to the Attio organization/deal.
7. Finish the run, add its activity, and let Attio sync the entity to Postgres.
8. A sweeper resumes stale unfinished runs.

The two email steps are tracked and retried independently, so a resume after
step 6 fails never re-sends the visitor's confirmation. Either step is
skipped — permanently, not retried — when there is no visitor address or no
`LEAD_MAGNET_EMAIL_FROM`/`LEAD_MAGNET_EMAIL_TO` configured; the lead is
already durable in Attio regardless.

The idempotency key (`tool|email|domain`) distinguishes a network replay from
a new duplicate using `submission_id`. A replay does not rerun the pipeline;
a later submission for the same identity returns HTTP `409`.

## Dependencies and configuration

The module shares PostgreSQL, AWS region, Firecrawl, and Attio configuration
with the backend. Tool-specific values use `LEAD_MAGNET_*`: Bedrock models,
allowed frame ancestors/origins, per-hour rate, sweeper timing, and the SES
sender/recipient pair (`LEAD_MAGNET_EMAIL_FROM`/`LEAD_MAGNET_EMAIL_TO`) for
the confirmation and internal-notice emails — both ship blank until the
sender identity is verified in SES and the internal distribution list is
confirmed. Production embedding also requires DNS, HTTPS, and the website
script tag. Leave the tools hostname DNS-only in Cloudflare so edge caching
does not delay `embed.js` deployments and rollbacks.

## Interfaces

| Endpoint | Processing |
| --- | --- |
| `POST /enrich` | Scrapes a supplied URL and enriches valuation inputs. |
| `POST /analyze` | Produces valuation analysis with a deterministic narrative fallback. |
| `POST /compare` | Runs peer searches with static-data shortfall fill. |
| `POST /submit-lead` | Computes and records the deterministic valuation submission. |
| `POST /benchmark` | Computes and records the benchmark result. |
| `POST /readiness/score` | Records the lead and requests the required Bedrock assessment. |
| `POST /buyer/apply` | Records a Buyer Network application and starts non-blocking qualification. |

Static pages are served under `/valuation/`, `/readiness/`, `/benchmark/`,
and `/buyers/`, with `/embed.js` for website integration.

### Valuation submission example

```http
POST /submit-lead
Content-Type: application/json

{
  "submission_id": "example-001",
  "company": "Example Manufacturing",
  "email": "owner@example.invalid",
  "revenue": 2500000,
  "cash": 100000,
  "debt": 250000,
  "consent": true
}
```

A successful response contains `run_id`, the `low`, `mid`, and `high`
valuation figures, and the contributing methods. Validation errors return
`422`, and rate limiting returns `429`. A later duplicate for the same identity
returns `409`. A network replay with the same submission ID is idempotent.

The browser should display the returned range once and retain the run context
for support. On `422`, it should identify the invalid input. On `429`, it
should ask the visitor to wait. On `409`, it must not imply that a second CRM
lead was created.

## Processing and failures

- A durable ledger row exists before AI or Attio work, so downstream failure
  does not lose the lead.
- Valuation and Benchmark return deterministic results when optional AI fails.
  Readiness returns a retryable error when required Bedrock assessment fails.
  Buyer Network still accepts the application if its internal note fails.
- Attio and stale-run failures are retried by the sweeper. Test submissions
  remain separated from production by `is_test`.
- Rate limits, validation, iframe origin policy, and idempotency errors are
  browser-visible and must be handled by each static page.
