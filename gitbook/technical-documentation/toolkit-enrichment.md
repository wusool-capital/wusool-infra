# Enrichment

## What it does

`/enrich-seller` and `/enrich-buyer` research public sources and propose values
for a role's empty fields. Enrichment never saves anything: **Review & Save**
opens the real edit form, prefilled, and the save follows the normal
[profile commands](toolkit-profile-commands.md) path.

## How it works

For a seller, three sources are tried in order. Each is asked only about the
fields the previous ones didn't resolve, and the first answer for a field is
final:

1. **Diffbot:** structured company data such as revenue, headcount,
   locations, founding date, description, headquarters, and social links.
2. **People Data Labs:** the same kind of data, as a second source for what
   Diffbot missed.
3. **Firecrawl and Bedrock:** a public web search, with Bedrock extracting
   values from the results. This is the last resort.

Buyers skip the first two: their enrichable fields (assets under management,
investment strategy, notable investments) aren't covered by either provider.

The research runs in the background. The result message lists every proposed
value with a confidence level and one **Review & Save** button.

## Basic tier

Seller discovery uses a lighter version that asks only the two structured
providers. It passes the company's domain when known, so a shared name
resolves to the right company. Each provider also reports the homepage of the company it
matched; discovery compares that with Google Maps before saving a lead.

## Failure behavior

- A provider without credentials is skipped; the others still run.
- A rate-limited response is logged as such, and retried once when the wait
  is short.
- Existing non-empty fields are never proposed over.

## Data it reads

Current values from `seller_roles`, `buyer_roles`, and `organizations`. It
writes nothing.

## Known gap

The People Data Labs response format hasn't been verified against a live
account yet. Diffbot's has.

## Code

`server/app/modules/enrichment` and its README.
