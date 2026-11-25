# Website API access

## What it does

The Astro website posts the Valuation, Readiness and Benchmark forms straight
from the visitor's browser to the lead-tool endpoints. This page covers who may
call them, what each call adds, and the limits that apply.

## Calls from the website

The six endpoints (`/enrich`, `/analyze`, `/compare`, `/submit-lead`,
`/readiness/score`, `/benchmark`) answer the `OPTIONS` preflight with `204`.
They send `Access-Control-Allow-Origin` only for origins in
`LEAD_MAGNET_ALLOWED_ORIGINS`.

- Origins match exactly: scheme, host, port, and no trailing slash.
- `POST` and the `Content-Type` header are allowed, with no credentials.
- An unlisted origin gets no CORS headers.

## Page source

The optional `analytics.page` field is a path of up to 200 characters, such as
`/valuation`. It is stored with the run on `tool_runs` and listed as "Page" in
the team notice email. A malformed value is dropped, never rejected.

## Company description lookup

`/enrich` reads the page's own `<meta name="description">` first, then
`og:description`, over plain HTTPS. It uses the text when it is 50 or more
characters and not just the page title. It then returns an empty `sector` for
the browser to pick. Only otherwise does it scrape with Firecrawl and ask the
model.

The fetch is guarded because the address comes from a public form:

- https and port 443 only.
- Private, loopback and link-local addresses are refused.
- At most three redirects, each checked the same way.
- At most 512 KB read, and a 5 second limit.

## Rate limits

Limits are per IP address per hour. The paid tool endpoints and report code
requests allow 20, report views and code checks 300, and PDF downloads 30. They
are held in memory, and the IP is taken from the last `X-Forwarded-For` entry.
