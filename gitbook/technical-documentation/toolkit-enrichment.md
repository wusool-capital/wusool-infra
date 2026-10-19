# Enrichment

## What it does

`/enrich-seller` and `/enrich-buyer` research public sources and propose values
for a role's empty fields. Enrichment never saves anything: **Review & Save**
opens the real edit form, prefilled, and the save follows the normal
[profile commands](toolkit-profile-commands.md) path.

## How it works

![How enrichment finds values](../.gitbook/assets/toolkit-enrichment-waterfall.svg)

For a seller, four sources are tried in order. Each is asked only about the
fields the previous ones didn't resolve, and the first answer for a field is
final:

1. **Diffbot:** structured company data such as revenue, headcount,
   locations, founding date, description, headquarters, and social links.
2. **People Data Labs:** the same kind of data, as a second source for what
   Diffbot missed.
3. **LinkedIn company page (Apify):** description, headquarters country,
   headcount band, founding year and logo. It runs only when the organization already has a
   LinkedIn URL and fields are still missing, because each run is billed.
4. **Firecrawl and Bedrock:** a public web search, with Bedrock extracting
   values from the results. This is the last resort.

For a buyer, the first three are asked only about the organization's fields.
Neither provider covers the buyer role's own fields, so those go straight to
the web search. They include investment strategy, target regions, check
sizes, and deal structure.

For a buyer, the command asks for the organization and then the vertical,
because each vertical is a separate buyer role. A buyer with one vertical
skips that step. Enrichment has no free-text note; only `/check-buyer` and
`/find-match` take one.

The research runs in the background. The result message lists every proposed
value with a confidence level and one **Review & Save** button. After the
edit form is saved, the button becomes "✅ ADDED by" the person who saved it.

## LinkedIn activity

After the proposal is posted, the bot replies in its thread with what it found
on LinkedIn for the role's contacts. A buyer's contact is its key contact. A
seller's contacts are the people on the organization, at most three, those
with a LinkedIn URL first.

- **Job changes:** the contact's current title or employer on LinkedIn differs
  from the CRM. A title that is blank in the CRM is never flagged.
- **Posts:** up to 10 per profile from the last month, including the
  company's own page.
- **No LinkedIn URL:** the contact is skipped, not searched by name, and named
  in the reply.

The reply comes after the proposal, so a slow or failing scrape never delays
the proposal. Nothing is written to the CRM from it. Nothing is stored yet
either. Storing it waits on the activities audit (AZM-150), so a re-run shows
last month's posts again.

Without an `APIFY_API_TOKEN`, the whole LinkedIn source is skipped.

Each Apify run logs its actor, item count, duration and outcome, which is the
cost signal. The scrapers are the HarvestAPI actors on Apify, called with a
60-second overall cap.

## Basic tier

Seller discovery uses a lighter version that asks only the two structured
providers (Diffbot and People Data Labs, never LinkedIn). It passes the company's domain when known, so a shared name
resolves to the right company. Each provider also reports the homepage of the company it
matched; discovery compares that with Google Maps before saving a lead.

## Failure behavior

- A provider without credentials is skipped; the others still run.
- A rate-limited response is logged as such, and retried once when the wait
  is short.
- Existing non-empty fields are never proposed over.
- Web-search values below 0.6 confidence are dropped rather than shown.

## Data it reads

Current values from `seller_roles`, `buyer_roles`, and `organizations`. It
writes nothing.

## Known gaps

- The People Data Labs response format hasn't been verified against a live
  account yet. Diffbot's has.
- The Apify output formats follow the actors' published examples and haven't
  been verified against a live run either.
- The free Apify plan limits the profile scraper to 50 runs in total. A pilot
  beyond that needs a paid plan and a monthly spend cap.

## Code

`server/app/modules/enrichment` and its README.
