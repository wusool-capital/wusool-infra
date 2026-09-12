# Filling in missing details — `/enrich-seller` and `/enrich-buyer`

These commands research a seller or buyer from public sources and propose
values for whatever fields are still empty — you review every proposal
before anything is saved.

1. Run `/enrich-seller <name>` or `/enrich-buyer <name>`.
2. If more than one organization matches the name, pick the right one from
   the list.
3. The bot posts a message listing every field it found a value for, each
   with a confidence level. This can take a little while — it's researching
   in the background, not blocking you.
4. Press **Review & Save**. This opens the same edit form you'd get from
   [`/edit-seller`/`/edit-buyer`](edit-profile.md), pre-filled with the
   proposed values.
5. Change anything you don't want to keep, then submit as usual. Nothing is
   written until you submit — a proposal on its own never touches Attio or
   the database.

## Example walkthrough

You run:

> `/enrich-buyer Raoof Capital`

A minute or so later, the bot posts:

> **Proposed enrichment for Raoof Capital**
>
> **investment_strategy**
> Proposed: Mid-market buyouts across the GCC, with a focus on
> manufacturing and logistics.
> Confidence: 90% — Sourced from Diffbot.
>
> **estimated_aum**
> Proposed: 450000000.0
> Confidence: 60% — Sourced from Diffbot.
>
> Review these values in the edit form before they're saved.
> `[Review & Save]`

You press **Review & Save**, which opens the same edit form `/edit-buyer`
would — pre-filled with both values. You clear `estimated_aum` since
you're not confident in that figure, then submit. Only
`investment_strategy` is saved.

If nothing public had supported any field — a common outcome for a
company with no clear public investment history — the bot instead posts:

> Raoof Capital
> No new field values found from public sources.

## Where else you'll see this suggested

- **On a `/find-match` result** — each seller in the shortlist carries a
  `/enrich-seller <name>` line, so you can fill in gaps for a specific
  candidate without leaving the match results.
- **After `/add-seller`** — the confirmation message for a newly-added
  seller suggests `/enrich-seller <name>` too, since a brand-new record is
  usually the one most worth researching.

## What it looks for

- **Sellers**: revenue, EBITDA, years active, location count, description,
  HQ country, employee range, founding date, LinkedIn, plus a handful of
  fields sourced from company-data providers (logo, AngelList, Facebook,
  Twitter).
- **Buyers**: investment strategy, notable investments, estimated AUM,
  target geography, and prior GCC acquisitions. These are specifically
  M&A/investment-firm facts — a company that isn't itself an investor
  (a product company, say) is unlikely to have any public answer to these,
  no matter how well-known it is.

Only fields that are currently empty are researched — a field that already
has a value is left alone.

## What it doesn't do

- It never invents a value with no source behind it — if nothing public
  supports a field, it's simply left out of the proposal.
- It never writes anything on its own. Every save still goes through the
  ordinary edit form, Attio first, then the database.
