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
   Nothing is recorded before this call.

`/analyze` and `/compare` run in parallel. After a 10-second loading screen,
the page shows a **Preliminary** valuation from the built-in sector tables.
It refines in place and is marked **Done** when both return. If they take
too long (about three minutes), the page settles on the preliminary figures
and submits them. It also submits when the visitor leaves the page.

## The valuation

The valuation is a simple average of up to five estimates:

- a discounted cash flow;
- trading comparables on EV/Revenue;
- trading comparables on EV/EBITDA;
- transaction comparables;
- industry research from VC rounds.

Trading comparables appear twice, so they carry double weight.

The AI's comparables, discounts, and DCF overrides from `/analyze` and
`/compare` feed straight into these figures. The built-in data, about 1,000
M&A deals, 127 VC rounds, and 31 comparable sectors, is what the page falls
back to.

- If `/analyze` judges the sector a poor fit, the page shows a "Sector
  reclassified" note. If the input can't identify the business, the
  visitor's own sector is kept.
- The visitor picks from 225 sectors, each mapped to one of the CRM's 85
  sector options. An unmapped sector raises an error rather than guessing.

## Differences from the old tool

The old browser tool was ported and diffed against the original over
thousands of generated cases. One difference is deliberate: Qatar and
Bahrain use 0%, the rate in the tool's own tax table. The old tool applied
20% by mistake, which undervalued every profitable business there.

## Failure behavior

If Bedrock fails, `/enrich` and `/compare` return 500, and the page carries
on with its built-in data. Search failures are tolerated on the server.
Either way, a valuation is always produced; failures only make it less
tailored.

## Status

`/submit-lead` is built and unit-tested but hasn't yet been verified end to
end against live Attio and the database.

## Code

`server/app/modules/lead_magnets`: the `valuation` folders under `domain`,
`application`, and `api`, and `static/valuation`.
