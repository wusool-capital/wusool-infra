# M&A Readiness

## What it does

A business owner answers 15 questions and gets a 0–100 readiness score, a
band, and recommendations. The team gets an internal advisory note.

## How it works

1. `POST /readiness/score` records the submission through the
   [write contract](lead-tools.md#the-write-contract).
2. Bedrock scores the answers and writes the recommendations and a note.
   This call is on the response path, so the visitor waits for it.
3. Deterministic rules, computed from the 13 scored answers, decide any
   referral and any hard flag, such as one customer exceeding half of
   revenue. The model's note is added to the rules' output, never replacing
   it.
4. The band is mapped to the CRM's readiness options: Early, Developing,
   Sale Ready, or Market Ready.

The two free-text answers, on what a buyer would want and what has held the
business back, reach the advisory note.

## Failure behavior

There is no non-AI score, by decision. If Bedrock fails, the visitor sees a
retryable error, but their submission is already recorded, so the lead is
kept.

## Differences from the old tool

The old tool only wrote to Attio after the AI call succeeded, so an AI
failure lost the lead. It also let the model's note replace the rules'
flags, so a "do not refer" warning could vanish.

## Status

Verified end to end against a real database and live Bedrock.

## Code

`server/app/modules/lead_magnets`: the `readiness` folders under `domain`
and `api`, and `static/readiness`.
