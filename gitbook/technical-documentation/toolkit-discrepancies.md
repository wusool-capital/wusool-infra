# Discrepancy check

## What it does

Checks a buyer role before a match for two things:

- **Conflicts:** does the advisor's typed note contradict what's on file for
  vertical, geography, ticket size, or EBITDA?
- **Missing details:** is anything the match needs absent from the profile?

It runs on its own through `/check-buyer <buyer>`, and inside `/find-match` as
the **Before we match** popup.

## How it works

1. **Read the note.** One Bedrock call parses the advisor's free-text note
   into every vertical it could mean, a region, countries, and ticket and
   EBITDA bounds. An empty note, or a buyer with nothing stored that could
   conflict, skips this call.
2. **Ground the amounts.** Any amount whose measure the note never names is
   dropped. Rules can only remove what the AI found, never add to it.
3. **Apply the rules:**
   - A vertical conflicts only when the stored one matches none of the
     note's possible meanings. A "Diversified / Generalist" vertical never
     conflicts.
   - A range conflicts only when it can't overlap the stored band; "at least
     $2M" never conflicts with $5–15M.
   - Geography is the target regions and countries combined. It is missing
     only when both are empty, and a stated place conflicts only when it
     falls outside both. Regions resolve to countries; "UAE" and "United
     Arab Emirates" match as one.
4. **Write the message.** A fixed template lists conflicts and missing
   details under separate headings, each naming the `/edit-buyer` field to
   fix, and ends with how the note was read.

## Failure behavior

If the note can't be read, the message still lists missing details and says
the note couldn't be checked. It never reports "no conflicts" in that case.
If the buyer search itself fails, the popup shows an error rather than an
all-clear.

## Data it reads

Buyer criteria only, through an interface the matching engine implements. The
check stores nothing.

## Code

`server/app/modules/discrepancies` and its README.
