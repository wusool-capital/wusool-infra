# Seller discovery

## What it does

Finds sellers outside the CRM through Google Maps when matching finds no
strong CRM seller. It checks each against the CRM and adds the ones that are
new and verified. It never writes to the CRM itself; it hands leads to
[profile commands](toolkit-profile-commands.md).

## How it works

1. **Search.** The search terms come from the match run's extracted
   requirements: the first sector and geography, with excluded sectors as
   filters. GCC, MENA, and MENATP resolve to a fixed country list, "Global"
   means no restriction, and other places are geocoded live. Places returns
   up to 20 results, and the first five that pass the pre-filter are used.
2. **Pre-filter against the CRM:**
   - An exact Google place or domain match is skipped as already in the CRM.
   - A name-only match isn't created. It is posted with **Add as seller**,
     so a person decides in the normal add form.
   - A lead already waiting for review is skipped for 30 days.
3. **Enrich.** New leads get the [basic enrichment tier](toolkit-enrichment.md#basic-tier).
4. **Check the website.** Each provider whose data would be saved must
   report a homepage matching the lead's Google Maps website. A match is the
   same host, ignoring `www.`, or a subdomain of it.
   - **All match, or no provider data to save:** the seller is created in
     one Attio-first write from the Google Maps details.
   - **Any mismatch, or no website to compare:** nothing is written. A **Website check**
     message shows both websites, and **Review & Save** opens the prefilled
     add-seller form.
5. **Report back.** Created sellers are added to the match run for review.
   Approving one creates a Qualified deal and posts a full enrichment
   proposal.

Pages on shared platforms count as no website, because they name the
platform rather than the company. These include Instagram, Facebook, Google
Sites, WordPress.com, Salla, Zid, Shopify, and link shorteners.

## Data it reads and writes

It owns one table, `discovery_reviews`, holding leads awaiting a website
review. A reviewed seller keeps its Google place ID, so later searches skip
it.

## Failure behavior

- Without Google Places credentials, discovery is disabled.
- A cap of 10 searches per buyer role per day guards against loops. A
  search that fails or finds nothing doesn't count. The cap is held in
  memory, so it resets on deploy.
- Enrichment of new leads runs two at a time, within a 45-second budget.
- Seller creation is serialized by an in-process lock, another reason the
  Toolkit runs as one instance.
- If the review store is down, or a lead has no place ID, the card uses a
  short-lived button instead. That lead isn't deduplicated.

## Code

`server/app/modules/discovery` and its README.
