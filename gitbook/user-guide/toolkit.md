# Wusool Toolkit

Wusool Toolkit is the deal team's Slack bot. Use it to find buyer–seller
matches, maintain buyer and seller profiles, and research missing details.
Its scores and research are decision support; always check the result.

## Before you start

- Use the bot in a channel it's in (add it with `/invite @Wusool Toolkit`).
  It doesn't work in direct messages.
- Type `/toolkit-help` to see the available commands.

| Command | Result |
| --- | --- |
| `/find-match <buyer name>` | Ranked seller shortlist |
| `/check-buyer <buyer name>` | Checks the buyer's profile for conflicts or missing details |
| `/edit-seller <name>` / `/edit-buyer <name>` | Edit an existing profile |
| `/add-seller <organization>` / `/add-buyer <organization>` | Add a role |
| `/enrich-seller <name>` / `/enrich-buyer <name>` | Propose missing values |
| `/toolkit-status` | Checks the bot is healthy |
| `/toolkit-help` | Command help |

## Check a buyer before matching

1. Run `/check-buyer <buyer name>` and confirm the buyer.
2. Optionally describe what this search is for, for example
   `pharma tech only, UAE, $5-15M ticket`.

**Expected result:** a popup lists **conflicts** with the buyer's profile and
**missing details**, each naming the `/edit-buyer` field to fix. It ends with
how your note was read, as a short list such as "Sector: Pharmaceuticals /
Biotech" and "Country: United Arab Emirates".

How your note is read:

- An amount counts as a ticket size only when you label it: "ticket",
  "check size", "investment", or "deal size".
- Open-ended amounts such as "at least $2M" conflict only when they can't
  overlap the buyer's range.
- The check compares four things with the buyer profile: sector, geography,
  ticket size, and EBITDA.
- It doesn't flag exclusions such as "no pharma", or an EV cap, revenue floor,
  or seller status. The match itself applies them.
- Geography uses the buyer's target regions and target countries together.

`/find-match` runs the same check before every match.

## Find matches

![Find matches flowchart](../.gitbook/assets/toolkit-find-match.svg)

1. Run `/find-match <buyer name>`, for example `/find-match Raoof Capital`.
2. If several buyers have similar names, select the intended record.
3. In the **Before we match** popup, choose **Run anyway**. If details are
   missing, press **Edit buyer** to fill just those fields in without leaving Slack, or
   **Cancel** to stop.
4. Use **View Full Analysis** to inspect a seller's reasoning, then choose
   **Approve Match** or **Reject Match**.

**Expected result:** a ranked shortlist with fit and data-confidence scores.

**Anything specific about this search?** What you type there outranks the
buyer's stored details. Name the business you want and put the modifier first.
"AI asset managers" finds asset or wealth managers and ranks AI ones higher.
"AI tools for asset managers" looks for AI companies serving them. Places,
ticket sizes ("ticket 5 to 10M") and exclusions ("not crypto") work too. If no
CRM seller fits, the bot says so and searches Google Maps instead of showing
sellers with no sector data.

### What your note can control

| You can set | Example | Effect |
|---|---|---|
| Business type | "AI asset managers" | Required sector. Modifiers such as AI only rank higher. |
| Places | "Saudi Arabia only", "UAE and Egypt" | Required geography. |
| Exclusions | "not crypto", "avoid real estate" | Removes sellers in that sector. |
| Revenue or EBITDA floor | "revenue above 5M" | Removes sellers below it. Sellers with no figure stay. |
| Ticket size | "ticket 5 to 10M" | Lowers the score of sellers outside the range. |
| Enterprise value cap | "EV below 50M" | Removes sellers above it. |
| Seller status | "Tier 1 sellers only" | Matches the seller's outreach tier, appetite signal or relationship status. |

Qualities such as founder background, runway or profitability appear in the
written explanation only. They don't change which sellers are shown or their
order.

The note can't change these:

- The shortlist is always three sellers.
- Google Maps search starts when no seller scores 50 or more.
- Each search adds up to five new sellers.
- Each buyer gets at most ten searches a day.
- Sellers already rejected for this buyer and vertical stay out.

**Approve Match** creates a Qualified Buy-side deal in Attio for that buyer
and seller. If an Inbound deal already exists for the pair, the bot asks
whether to promote it to Qualified or create a new one. An approval can't be
undone from Slack; ask the CRM owner to change the deal in Attio. Matching
never contacts an organization.

**Reject Match** keeps that seller out of later matches for the same buyer
and vertical. It still appears for other buyers, and the seller stays in
the CRM. A rejection can't be undone from Slack.

### When no CRM seller is a strong fit

The bot searches Google Maps for new sellers in the buyer's target regions
and countries:

- Each search writes up to five new sellers. It checks the Google Maps
  results in order and keeps going until it has five or runs out.
- A lead is saved automatically when its researched details match its Google
  Maps website. It is also saved when there are no extra details to check.
- A lead whose researched website doesn't match is skipped, and the result
  message says how many. Nothing is written for it.
- A lead whose name resembles a company already in the CRM is skipped too,
  and the message counts those. If one was really a different company, add
  it with `/add-seller`.
- A lead already waiting on an older **Website check** message is skipped for
  30 days. Those older messages still work.
- Pages on Instagram, Facebook, Shopify, Salla, Zid, or Google Sites count
  as "no website".


### If matching does not work

- **Buyer not found:** use the exact Attio name or add it with `/add-buyer`.
- **Thin or low-confidence result:** run `/enrich-buyer` or
  `/enrich-seller`, review the proposal, and match again.
- **Unexpected countries in web leads:** set the buyer's target regions or
  countries with `/edit-buyer`.
- **Error or timeout:** check `/toolkit-status`, then see
  [Troubleshooting](troubleshooting.md).

## Maintain buyer and seller records

### Edit an existing profile

![Edit a profile flowchart](../.gitbook/assets/toolkit-edit-profile.svg)

1. Run `/edit-seller <name>` or `/edit-buyer <name>` and select the intended
   record if asked.
2. For a buyer, pick a vertical. An existing one edits that role.
3. Tick only the organization or profile fields you need to change.
4. Continue to the pre-filled form, update the values, and press **Save**.

**Expected result:** the bot confirms the update once it is saved to Attio.
If only part of it saved, the bot says which part.

Scores, pipeline values, and people references can't be edited from Slack.

### Add a buyer or seller

![Add a buyer or seller flowchart](../.gitbook/assets/toolkit-add-role.svg)

1. Run `/add-seller <organization name>` or `/add-buyer <organization name>`.
2. Select an existing organization if it is the same business. Otherwise
   choose **None of these — create new organization**.
3. For a buyer, pick a vertical. An organization can hold one buyer role per
   vertical: an existing one edits that role, and an unused one creates a new
   role.
4. Complete the form. A new organization only needs a name; other fields can
   be filled later.
5. Review duplicate warnings and press **Save**.

**Expected result:** the organization and role appear in Attio.

There is no `/remove-seller` or `/remove-buyer`. Ask the CRM owner to remove
a role in Attio.

## Research missing details

![Research missing details flowchart](../.gitbook/assets/toolkit-enrich.svg)

1. Run `/enrich-seller <name>` or `/enrich-buyer <name>` and select the
   intended record if asked. For a buyer, pick the organization, then the
   vertical. You can add a note under **Anything specific about this
   search?** to steer the research.
2. The bot researches public company sources and lists proposed values with
   confidence levels.
3. Press **Review & Save**, correct or clear anything you don't want, and
   submit the normal edit form. Once saved, the button changes to
   "✅ ADDED by" with your name.

**Expected result:** only reviewed values are saved. Fields that already
have a value are never overwritten.
