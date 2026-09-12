# Finding matches — `/find-match`

1. Run `/find-match <buyer name>` (for example `/find-match Gulf Holdings`).
2. If the name matches more than one buyer, pick the right one from the list.
   If nothing matches, the bot tells you and stops.
3. The bot works through the buyer's requirements, compares every eligible
   seller, and posts a **ranked shortlist** with a score for each.
4. Each result carries buttons:
   - **Approve Match** — records your decision to take the match forward.
   - **Reject Match** — records that the match is not suitable.
   - **View Full Analysis** — shows the detailed reasoning behind the score.

   A line under each result also suggests `/enrich-seller <name>` if that
   candidate's profile still has gaps worth researching. See
   [Filling in missing details](enrich.md).

## Example walkthrough

```
/find-match Raoof Capital
        │
        ▼
 Score every eligible seller in the CRM
        │
        ├──▶ Al Noor Manufacturing — 82/100  ──▶ [Approve Match] ──▶ done
        │
        └──▶ Falcon Steel Works — 58/100     ──▶ [Reject Match] ──▶ done
```

You run `/find-match Raoof Capital`. The bot scores every eligible seller
already in the CRM and posts:

> **Buyer:** Raoof Capital
>
> **1. Al Noor Manufacturing — 82/100**
> Data confidence: 74/100
> Strong sector and size fit — CRM data confirms both revenue and
> geography.
> `[View Full Analysis]` `[Approve Match]` `[Reject Match]`
> Run `/enrich-seller Al Noor Manufacturing` to research missing fields.
>
> **2. Falcon Steel Works — 58/100**
> Data confidence: 40/100
> Sector fit only — most financial fields are still empty.
> `[View Full Analysis]` `[Approve Match]` `[Reject Match]`
> Run `/enrich-seller Falcon Steel Works` to research missing fields.

You review the reasoning behind each score, then press **Approve Match**
on Al Noor Manufacturing to take it forward.

## Reading the result

- **Score** — an overall fit percentage. Higher is better. It combines
  strategy fit, size fit, and sector fit.
- **Confidence** — shown separately from the score. It reflects how much of
  the assessment rests on real CRM data rather than the model's own
  inference. A high score with low confidence means "promising, but the
  profile is thin — verify before acting."
- **No strong match** — if every seller scores below the internal threshold,
  the bot also posts up to **three web-sourced leads**, found via a public
  search rather than existing CRM records:

  ```
  /find-match <buyer>
          │
          ▼
   No CRM seller clears the threshold
          │
          ▼
   Search the public web for leads
          │
          ├──▶ Delta Logistics ──▶ [Add as seller] ──▶ /add-seller flow
          │
          └──▶ [Find more sellers] ──▶ re-runs the search
  ```

  > Found 2 potential seller(s) from public sources. **Not yet in CRM,
  > unverified.**
  >
  > **1. Delta Logistics**
  > 4200 Industrial Way, Dubai
  > `[View on Maps]` `[Add as seller]`

  A **Find more sellers** button on the result lets you re-run that search
  on demand, too.
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
