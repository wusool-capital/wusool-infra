# Advisor's note in a match

The advisor's note on `/find-match` changes how the
[matching engine](toolkit-matching.md) runs. This page lists what the note can
control.

## What the advisor's note controls

Only criteria in the engine's registry reach scoring: revenue, EBITDA,
geography, sector, sector exclusion, outreach tier, relationship status, and
appetite signal. A confirmed advisor row for any of them replaces the stored
value and eliminates on a populated field that contradicts it.

- **Narrowing in SQL:** sector, geography, and EV ceiling.
- **Score only:** ticket size, through the advisor limits.
- **Explanation only:** anything else, such as founder background or runway,
  folded into the buyer summary the reasoning call reads.
- **Not controllable:** the shortlist size, the discovery threshold, the five
  leads per search, the daily search cap, and sellers already rejected.

The [discrepancy check](toolkit-discrepancies.md#what-it-shows-but-doesnt-compare)
compares only four of these with the buyer profile: sector, geography,
ticket size, and EBITDA.

The seller-field criteria accept only the exact CRM options. The code copies
those options, and `tests/test_seller_select_vocabulary.py` checks the copy.
A row whose value isn't an option is dropped, so free text such as "regional
founders" never scores against them. The code also drops a soft sector that
only repeats the buyer's stored sector. It strips place names and unnamed
stored sector words from the Maps search phrase.
