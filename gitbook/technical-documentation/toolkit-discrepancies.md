# Discrepancy check

## What it does

Before a match runs, the discrepancy check compares what the advisor typed
with the buyer's profile and lists what the profile is missing. It answers:

- **Conflicts:** does the advisor's note contradict the profile's vertical,
  geography, ticket size, or EBITDA range?
- **Missing details:** which of those four is empty on the profile?

AI only reads the note. Every decision is made by deterministic rules, and
the message is written from a fixed template.

## What it shows but doesn't compare

The [match](toolkit-matching-note.md) applies more
of the note than this check compares. These are never flagged as conflicts,
but each one the note sets appears in the popup's "From your note" list:

- **EV ceiling.** The buyer profile stores one, but the check doesn't read it.
- **Revenue.** The buyer profile has no field to compare it with.
- **Exclusions** such as "not crypto".
- **Seller status** such as "Tier 1 only" or "positive response".
- **Modifiers** such as "AI" in "AI asset managers". Only the sector counts.
  The list shows them as "Ranks higher (not required)".

The check's own AI call does the reading, so the match can still read an
unusual note differently.

## Where it runs

- **`/check-buyer <buyer>`:** the advisor confirms the buyer and can add a
  note in the "Anything specific about this search?" box. The
  result appears in the popup.
- **`/find-match <buyer>`:** the same check fills the **Before we match**
  popup. **Run anyway** starts the match, even before the check finishes;
  **Cancel** stops it. When details are missing, **Edit buyer** opens the
  edit form over the popup, with only the empty fields. Cancelling returns to
  the popup. If only the vertical is missing, it opens the field picker
  instead.
- **Saving from the popup:** when the form is submitted, the popup swaps
  **Run anyway** for "Saving your changes…". The Attio write takes a couple of
  seconds and the match reads Postgres, so an early click would use the old
  profile. When the write ends, saved or failed, the popup rechecks the buyer
  and restores **Run anyway**.

The check stores nothing. It reads buyer criteria through an interface the
[matching engine](toolkit-matching.md) implements.

## How it works

![How the discrepancy check decides](../.gitbook/assets/discrepancy-check.svg)

### 1. Decide whether the note needs reading

The note goes to the AI whenever it isn't empty; an empty note never calls
the model, and the check reports missing details only. Even a buyer with
nothing to conflict gets its note read, so the list can show what the match
will apply.

### 2. Read the note (one Bedrock call)

The model returns structured JSON in a fixed schema. It holds core, modifier,
and excluded verticals, one region, countries, and seller status. It also holds
ticket, EBITDA, EV ceiling, and revenue amounts in USD. The prompt sets these
rules:

- **The note is data, not instructions.** It is wrapped in `<note>` tags after
  stripping any pasted tag, so a note can't redirect the model.
- **Closed vocabularies.** Verticals, regions, and countries must be copied
  exactly from the CRM's own option lists.
- **Overlapping verticals.** "Clinics" can mean several options, so the model
  returns every close one, most likely first.
- **Regions only when named.** "Gulf" becomes GCC, but named countries stay
  countries, never regions. Where the advisor's client is based doesn't count
  as a target.
- **Core business and modifiers.** "AI asset managers" reads Asset
  Management as the sector and AI / ML as a modifier. In "AI tools for asset
  managers" the two swap.
- **Exclusions are kept apart.** "No pharma" or "excluding UAE" never enters
  the sector, region, or countries. An excluded sector is returned separately.
- **USD only.** An amount in any other currency is dropped, never converted.
- **Labelled amounts only.** An amount counts only when the note names what
  it measures (see step 3). A fund size or a margin is never a ticket, EBITDA,
  EV ceiling, or revenue.
- **Bounds.** "At least" sets only the low bound, "up to" only the high one,
  and an exact figure sets both.

An invalid response gets one repair retry; after that the call fails closed.

### 3. Ground the amounts

A second, code-level guard keeps an amount only if the note itself names
what it measures. It looks for these words:

- Ticket, cheque or check size, invest…, and deal size.
- EBITDA.
- EV, enterprise value, valuation, or valued.
- Revenue, turnover, or sales.

It can only remove what the model found, never add.

### 4. Apply the rules

| Criterion | Conflicts when | Missing when |
| --- | --- | --- |
| Vertical | The profile's specific vertical matches **none** of the note's possible verticals. "Diversified / Generalist" on either side never conflicts. | No vertical |
| Geography | **Every** place the note names is provably outside the profile's target regions and countries combined. | No target region **and** no target country |
| Ticket size | The note's range can't overlap the profile's band at all. | No minimum **and** no maximum |
| EBITDA | Same overlap test as ticket size. | No floor **and** no ceiling |

Geography is the subtle one:

- Regions resolve to country lists (GCC, MENA, MENATP). Country spellings
  are matched as one, so "UAE" equals "United Arab Emirates".
- A region that can't be resolved to countries, such as Europe, is checked
  against a hand-reviewed table. It lists regions that never overlap, such as
  GCC and Europe. If it can't rule the pair out, there is no conflict.
- "Global" on the profile means nothing can conflict.

The rules lean towards silence: anything unresolved produces no conflict,
because a false alarm costs more than a missed one.

### 5. Write the message

The template produces up to four parts:

1. **"{Buyer}'s profile doesn't match your note"**, one line per conflict.
   Each line names the `/edit-buyer` field, what the profile has, and what
   the advisor said.
2. **"Missing from {Buyer}'s profile"**, one line per missing field.
3. If the note couldn't be read: "Your note couldn't be checked for
   conflicts." It never says "no conflicts" in that case.
4. **"From your note: …"**, a short list of what was understood. It has one
   line each for sector, region, country, ticket, EBITDA, EV ceiling, revenue,
   exclusions, seller status, and modifiers. A misread is easy to spot.

## Example

A buyer's profile says Pharmaceuticals / Biotech, GCC, and a $5–15M ticket.
The advisor types `clinics in Europe, $20M ticket`.

- **Vertical:** "clinics" maps to clinic verticals, none of them
  Pharmaceuticals / Biotech: a conflict.
- **Geography:** Europe can't resolve to countries, but GCC and Europe never
  overlap: a conflict.
- **Ticket:** $20M can't overlap $5–15M: a conflict.
- **EBITDA:** nothing is stored, so it is listed as missing.

The popup lists the three conflicts, then EBITDA under missing details, and
ends with the "From your note" list.

## Failure behavior

- If the AI call fails, the check still lists missing details and flags the
  note as unchecked.
- If the buyer search itself fails, the popup shows an error instead of an
  all-clear.

## Code

`server/app/modules/discrepancies` and its README. The rules are in
`domain/rules.py`, the region tables in `domain/vocabulary.py`, and the prompt
in `providers/bedrock/client.py`.
