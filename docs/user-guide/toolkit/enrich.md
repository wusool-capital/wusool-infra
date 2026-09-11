# Filling in missing details — `/enrich-seller` and `/enrich-buyer`

These commands research a seller or buyer from public sources and propose
values for whatever fields are still empty — you review every proposal
before anything is saved.

1. Run `/enrich-seller <name>` or `/enrich-buyer <name>`.
2. If more than one organization matches the name, pick the right one from
   the list.
3. The bot posts a message listing every field it found a value for, each
   with the source it drew the value from and a confidence level. This can
   take a little while — it's researching in the background, not blocking
   you.
4. Press **Review & Save**. This opens the same edit form you'd get from
   [`/edit-seller`/`/edit-buyer`](edit-profile.md), pre-filled with the
   proposed values.
5. Change anything you don't want to keep, then submit as usual. Nothing is
   written until you submit — a proposal on its own never touches Attio or
   the database.

## Where else you'll see "Enrich"

- **On a `/find-match` result** — each seller in the shortlist has its own
  **Enrich** button, so you can fill in gaps for a specific candidate
  without leaving the match results.
- **After `/add-seller`** — the confirmation message for a newly-added
  seller carries an **Enrich** button, since a brand-new record is usually
  the one most worth researching.

## What it looks for

- **Sellers**: revenue, EBITDA, years active, location count, description,
  HQ country, employee range, founding date, LinkedIn, plus a handful of
  fields sourced from company-data providers (logo, AngelList, Facebook,
  Twitter).
- **Buyers**: investment strategy, notable investments, estimated AUM,
  target geography, and prior GCC acquisitions.

Only fields that are currently empty are researched — a field that already
has a value is left alone.

## What it doesn't do

- It never invents a value with no source behind it — if nothing public
  supports a field, it's simply left out of the proposal.
- It never writes anything on its own. Every save still goes through the
  ordinary edit form, Attio first, then the database.
