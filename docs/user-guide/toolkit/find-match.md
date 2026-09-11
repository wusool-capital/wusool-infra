# Finding matches — `/find-match`

1. Run `/find-match <buyer name>` (for example `/find-match Gulf Holdings`).
2. If the name matches more than one buyer, pick the right one from the list.
   If nothing matches, the bot tells you and stops.
3. The bot works through the buyer's requirements, compares every eligible
   seller, and posts a **ranked shortlist** with a score for each.
4. Each result carries buttons:
   - **Approve** — records your decision to take the match forward.
   - **Reject** — records that the match is not suitable.
   - **View Full Analysis** — shows the detailed reasoning behind the score.
   - **Enrich** — researches that seller and proposes values for whatever
     fields are still empty. See
     [Filling in missing details](enrich.md).

## Reading the result

- **Score** — an overall fit percentage. Higher is better. It combines
  strategy fit, size fit, and sector fit.
- **Confidence** — shown separately from the score. It reflects how much of
  the assessment rests on real CRM data rather than the model's own
  inference. A high score with low confidence means "promising, but the
  profile is thin — verify before acting."
- **No strong match** — if every seller scores below the internal threshold,
  the bot also posts up to **three web-sourced leads**, found via a public
  search rather than existing CRM records. A **Find more sellers** button on
  the result lets you re-run that search on demand, too.
  - Each lead has its own button to turn it into a real seller record: it
    opens the same [`/add-seller`](add-buyer-seller.md) flow, pre-filled
    with whatever the lead's details support — including checking first
    whether a matching organization already exists, so you're never
    offered a duplicate.

## What `/find-match` does not do

- It never contacts a buyer or seller.
- It never changes a deal, a profile, or any pipeline field.
- It does not read uploaded documents or search the open web beyond the
  above lead search when no strong CRM match exists.

Approve / Reject can be pressed by anyone who sees the message; the bot
re-checks the current data before saving, so a decision is never based on a
stale message.
