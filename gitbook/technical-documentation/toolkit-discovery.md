# Seller discovery

## What it does

Finds sellers outside the CRM through Google Maps when matching finds no
strong CRM seller. It checks each against the CRM and adds the ones that are
new and verified. It never writes to the CRM itself; it hands leads to
[profile commands](toolkit-profile-commands.md).

## How it works

1. **Search.** Google Places searches the buyer's sector in the buyer's
   target regions and countries. GCC, MENA, and MENATP resolve to a fixed
   country list, "Global" means no restriction, and other places are
   geocoded live. Places returns up to 20 results per call.
2. **Pre-filter against the CRM:**
   - An exact Google place or domain match is skipped as already in the CRM.
   - A name-only match isn't created. It is posted with **Add as seller**,
     so a person decides in the normal add form.
   - A lead already waiting for review is skipped for 30 days.
3. **Enrich.** New leads get the [basic enrichment tier](toolkit-enrichment.md#basic-tier).
4. **Check the website.** Each provider that contributed data must report a
   homepage matching the lead's Google Maps website (same host, ignoring
   `www.`, or a subdomain of it).
   - **All match:** the seller is created in one Attio-first write.
   - **Any mismatch, or no website:** nothing is written. A **Website check**
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
- A daily search cap per buyer role guards against loops. It is held in
  memory, so it resets on deploy.
- If the review store is down, or a lead has no place ID, the card uses a
  short-lived button instead. That lead isn't deduplicated.

## Code

`server/app/modules/discovery` and its README.
