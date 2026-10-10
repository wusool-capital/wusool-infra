# Valuation

## What it does

A business owner enters their figures and gets a low, mid, and high valuation
with the methods behind it. The report adds a strategic read of the business.

## How it works

The page calls three stateless endpoints while the visitor is still in the
tool, then records the result:

1. **`POST /enrich`** scrapes the company's website with Firecrawl, and
   Bedrock extracts inputs from it.
2. **`POST /analyze`** has Bedrock judge the sector fit, discounts, DCF
   overrides, a strategic read, and a readiness scorecard. If it fails, a
   deterministic pros, cons, and insights summary is used instead.
3. **`POST /compare`** has Bedrock plan peer searches, Firecrawl run them,
   and Bedrock pick the comparables. Gaps are filled from built-in data.
4. **`POST /submit-lead`** computes the final valuation with no AI call and
   records it through the [write contract](lead-tools.md#the-write-contract).

`/analyze` and `/compare` run in parallel. After a 10-second loading screen,
the page shows a **Preliminary** valuation from the built-in sector tables.
It refines in place and is marked **Done** when both return. If they take
too long, the page settles on the preliminary figures.

## The valuation

Four methods are blended: a discounted cash flow, trading comparables,
transaction comparables, and a venture-capital method. The built-in data
holds about 1,000 M&A deals, 127 VC rounds, and 31 comparable sectors.

- If `/analyze` judges the sector a poor fit, the page shows a "Sector
  reclassified" note. If the input can't identify the business, the
  visitor's own sector is kept.
- The visitor picks from 225 sectors, each mapped to one of the CRM's 85
  sector options. An unmapped sector raises an error rather than guessing.

## Differences from the old tool

The old browser tool was ported and diffed against the original over
thousands of generated cases. One difference is deliberate: Qatar and
Bahrain are taxed at 0%, their real rate. The old tool taxed them at 20% by
mistake, which undervalued every profitable business there.

## Failure behavior

Every AI step has a fallback, so a valuation is always produced. AI and
search failures only make the report less detailed.

## Status

`/submit-lead` is built and unit-tested but hasn't yet been verified end to
end against live Attio and the database.

## Code

`server/app/modules/lead_magnets`: the `valuation` folders under `domain`,
`application`, and `api`, and `static/valuation`.
