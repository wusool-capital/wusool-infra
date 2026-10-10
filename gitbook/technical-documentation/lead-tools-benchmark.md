# GCC SME Benchmark

## What it does

A business compares its figures with GCC peers. The visitor sees percentiles
per metric, an overall score and band, and a short narrative. Tech mode also
shows an implied enterprise value. No AI is involved.

## How it works

1. `POST /benchmark` records the submission through the
   [write contract](lead-tools.md#the-write-contract).
2. The figures are scored against a built-in peer dataset. SME mode compares
   by sector and revenue band; tech mode compares by sector and funding
   stage.
3. The score maps to a band, from "Top decile operator" down.
4. Templated paragraphs explain the metrics that stand out.

The page offers an AED or USD toggle for entry and display only. Everything
is computed and stored in USD.

## Internal triage

The team also gets fields the visitor never sees, on the seller role in Attio.
These are lead priority, routing reason, quality checks, benchmark review,
headline flag, and band.

## Accuracy

The engine was ported from the old browser tool and diffed against it over
about 20,000 generated cases with no mismatches. That comparison caught a
rounding difference: JavaScript rounds halves up, Python to even. The
server uses JavaScript's rounding so scores match what visitors saw before.

## Status

Verified end to end against a real database.

## Code

`server/app/modules/lead_magnets`: the `benchmark` folders under `domain`
and `api`, and `static/benchmark`. The peer dataset and report copy are
generated files; don't edit them by hand.
