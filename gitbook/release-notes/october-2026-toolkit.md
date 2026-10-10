# October 2026: Wusool Toolkit

Delivery period: 15 September – 10 October 2026.

## Approved matches become deals

- **Approve Match** now creates a Qualified Buy-side deal in Attio and links
  it to the match. Advisors no longer re-key approved matches into the
  pipeline.
- If a deal already exists for that buyer and seller, the bot asks whether
  to promote it or create a new one. Pipelines don't fill with duplicates.
- If Attio saves the deal but the database doesn't, the advisor is told
  exactly what was saved, and the nightly sync completes the rest.

## The discrepancy check (new)

- **New `/check-buyer` command.** It compares what an advisor is looking for
  with the buyer's stored profile, before any match runs.
- **"Before we match" popup.** Every `/find-match` now opens it, listing
  conflicts and missing details under separate headings, each naming the
  field to fix. The match starts only on **Run anyway**.
- **Understands everyday notes.** AI reads a note such as "Pharma tech only,
  UAE, $5-15M ticket". Fixed rules then check it and write the message, so the
  wording is consistent and never invents a problem.
- **Fewer false alarms.**
  - Amounts count only when labelled as a ticket or EBITDA.
  - Open-ended amounts only conflict when they can't overlap.
  - Overlapping sectors such as "clinics" are handled.
  - Regions only conflict when they truly can't overlap.
- **Shows its reading.** Every message ends with "Read your note as: …", so
  a misread is easy to spot. If the note can't be read, it says so instead
  of reporting an all-clear.

## Smarter matching

- **Narrowing first.** Matching narrows sellers in the database by the
  buyer's sector, region, country, and valuation ceiling before scoring. A
  pharma buyer is no longer scored against industrial sellers, and the old
  1,000-seller cap is gone.
- **Regions and countries together.** A GCC buyer now matches sellers tagged
  "UAE" or "KSA". A buyer targeting GCC plus Egypt keeps sellers from either.
  Spelling differences such as Turkey and Türkiye now match.
- **The advisor's note wins.** "Egypt" for a buyer stored as US runs the
  search on Egypt. A stated ticket size or valuation cap replaces the stored
  one for that run, and "Run anyway" keeps the note.
- **Partial stakes.** Sellers valued above a buyer's cheque size stay in the
  pool with a lower score, because a cheque can buy a partial stake.
- **Clean-up.** A scoring criterion that never matched anything was retired,
  and discovered sellers are numbered in their own message.

## Seller discovery creates sellers

- **Automatic creation.** Discovery now creates sellers instead of only
  suggesting them. Each search checks up to 20 Google Maps results, skips
  those already in the CRM, and adds the first five new ones.
- **Ready to approve.** New sellers are filled in with company data and
  posted with Approve and Reject. Approving opens a Qualified deal and posts
  a full research proposal for review.
- **Website verification.** A seller is saved automatically only when its
  researched website matches Google Maps. Otherwise a **Website check**
  message lets a person review and save it.
- **Duplicates go to a person.** A result that only resembles an existing
  company gets an **Add as seller** button instead of being created.
- **Safeguards.** A lead already waiting for review is skipped for 30 days.
  Social and shop pages count as "no website". Each buyer gets at most 10
  searches a day.
- **Better geography.** Searches cover every target region and country.
  GCC and MENA resolve correctly; before, "GCC" could geocode to a college in
  California.

## Buyer and seller profiles

- **One profile per sector.** A buyer can now hold one buyer profile per
  sector. `/add-buyer` and `/edit-buyer` ask for the sector first, so a
  buyer hunting five industries can be matched on each one separately.
- `/edit-buyer` lists each organization once and edits the right profile in
  Attio.
- Company lookups pass the website to the data providers, for more accurate
  results.
- Removed organizations no longer appear in searches, matches, or edits.
