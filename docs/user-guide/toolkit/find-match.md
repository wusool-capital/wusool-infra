# Finding matches — `/find-match`

1. Run `/find-match <buyer name>` (for example `/find-match Gulf Holdings`).
2. If the name matches more than one buyer, pick the right one from the list.
   If nothing matches, the bot tells you and stops.
3. The bot works through the buyer's requirements, compares every eligible
   seller, and posts a **ranked shortlist** with a score for each.
4. Each result carries three buttons:
   - **Approve** — records your decision to take the match forward.
   - **Reject** — records that the match is not suitable.
   - **View Full Analysis** — shows the detailed reasoning behind the score.

![A ranked shortlist posted by `/find-match`, with Approve, Reject and View Full Analysis buttons on each result.](../../images/toolkit-find-match-shortlist.png)

## Reading the result

- **Score** — an overall fit percentage. Higher is better. It combines
  strategy fit, size fit, and sector fit.
- **Confidence** — shown separately from the score. It reflects how much of
  the assessment rests on real CRM data rather than the model's own
  inference. A high score with low confidence means "promising, but the
  profile is thin — verify before acting."
- **No strong match** — if every seller scores below the internal threshold,
  the bot instead shows up to **three unverified leads** found on Google
  Maps. These are suggestions only: they are not saved and are shown once.

![The View Full Analysis panel, showing the detailed reasoning behind a match score.](../../images/toolkit-find-match-full-analysis.png)

## What `/find-match` does not do

- It never contacts a buyer or seller.
- It never changes a deal, a profile, or any pipeline field.
- It does not read uploaded documents or search the open web beyond the
  single Google-Maps fallback above.

Approve / Reject can be pressed by anyone who sees the message; the bot
re-checks the current data before saving, so a decision is never based on a
stale message.
