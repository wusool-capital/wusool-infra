# Wusool Toolkit — User Guide

The Wusool Toolkit is a Slack bot for the deal team. It has five slash
commands for finding buyer–seller matches and for keeping buyer and seller
profiles up to date.

Everything happens inside Slack — there is no separate website or login. The
bot reads and writes the same customer data the team uses in Attio and in the
Wusool database.

> **Which data the bot uses:** the bot works against the **DEV Attio
> workspace** and the shared Wusool database. Changes you make with `/edit-*`
> and `/add-*` appear in Attio first, then in the database a moment later.

## Commands at a glance

| Command | What it does |
| --- | --- |
| `/find-match <buyer name>` | Finds and scores the sellers that best fit a buyer, and posts a ranked shortlist. |
| `/edit-seller <name>` | Edit an existing seller's profile (and, optionally, its organization's details). |
| `/edit-buyer <name>` | Edit an existing buyer's profile (and, optionally, its organization's details). |
| `/add-seller <organization name>` | Register a new seller, attaching it to an existing organization or creating a new one. |
| `/add-buyer <organization name>` | Register a new buyer, attaching it to an existing organization or creating a new one. |

Type the command in any channel or direct message where the bot is present.
Replies are only visible to you.

---

## Finding matches — `/find-match`

1. Run `/find-match <buyer name>` (for example `/find-match Gulf Holdings`).
2. If the name matches more than one buyer, pick the right one from the list.
   If nothing matches, the bot tells you and stops.
3. The bot works through the buyer's requirements, compares every eligible
   seller, and posts a **ranked shortlist** with a score for each.
4. Each result carries three buttons:
   - **Approve** — records your decision to take the match forward.
   - **Reject** — records that the match is not suitable.
   - **View Full Analysis** — shows the detailed reasoning behind the score.

### Reading the result

- **Score** — an overall fit percentage. Higher is better. It combines
  strategy fit, size fit, and sector fit.
- **Confidence** — shown separately from the score. It reflects how much of
  the assessment rests on real CRM data rather than the model's own
  inference. A high score with low confidence means "promising, but the
  profile is thin — verify before acting."
- **No strong match** — if every seller scores below the internal threshold,
  the bot instead shows up to **three unverified leads** found on Google
  Maps. These are suggestions only: they are not saved and are shown once.

### What `/find-match` does not do

- It never contacts a buyer or seller.
- It never changes a deal, a profile, or any pipeline field.
- It does not read uploaded documents or search the open web beyond the
  single Google-Maps fallback above.

Approve / Reject can be pressed by anyone who sees the message; the bot
re-checks the current data before saving, so a decision is never based on a
stale message.

---

## Editing a profile — `/edit-seller` and `/edit-buyer`

1. Run `/edit-seller <name>` or `/edit-buyer <name>`. Pick the right record
   if the name is ambiguous.
2. **Choose the fields to change.** A form lists the editable fields, grouped
   into *Organization* and *Seller/Buyer profile*. Tick only what you need.
3. **Edit the values.** The next form shows just those fields, pre-filled
   with their current values.
4. **Submit.** The bot writes to Attio first, then the database. If a write
   fails partway, the confirmation message tells you exactly what was saved
   and what was not.

### Fields you cannot edit from Slack

Some fields are intentionally left out of the edit form:

- System-managed values such as an organization's connection strength.
- Scores and enrichment fields (readiness score, lead-quality score, deals
  introduced / converted) — these are set by other processes and need
  sign-off before they can be edited here.
- People/user references such as an organization's owner or a buyer's key
  contact — there is no person picker in the form yet.
- `Intake source` can be changed, but only after ticking the "this is a
  correction" box.

---

## Adding a buyer or seller — `/add-seller` and `/add-buyer`

1. Run `/add-seller <organization name>` or `/add-buyer <organization name>`.
2. **Pick the organization.** If similar organizations already exist, choose
   one to attach the new role to, or choose "create new". If the organization
   you pick already has that role, the bot stops and points you to `/edit-*`
   instead.
3. **Fill in the form.** Every field is optional except the name of a brand
   new organization. If you are creating a new organization that looks like a
   duplicate, the form warns you but still lets you continue.
4. **Submit.** The bot creates the organization (if new) and the role in
   Attio first, then the database.

---

## Important rules and limitations

- **Attio is written first.** Every `/edit-*` and `/add-*` change lands in
  the DEV Attio workspace before the database. This keeps the scheduled
  Attio → database sync from overwriting your change.
- **There is no `/remove-seller` or `/remove-buyer`.** Removing a role is not
  done through the bot.
- **Anyone in the workspace can run these commands.** There is no
  per-user permission list.
- **Two people adding the same organization at the same time** can each
  succeed and create a duplicate. Coordinate before bulk-adding.
- **The first time a command is run against a real organization is the first
  real test for that organization.** There is no practice mode — check the
  Attio record and, for matches, the posted result afterward.

---

## Other tools

- **n8n** (`https://n8n-dev.wusoolcapital.com/`, `https://n8n.wusoolcapital.com/`)
  is the workflow-automation platform. It has its own login and its own
  [documentation](https://docs.n8n.io/). Invite users from **Settings →
  Users** inside n8n.
- **Attio** is the CRM of record for the business team. The bot writes into
  it; it is not managed from this repository.

## Getting help

Contact the engineering owner (see the repository `CODEOWNERS` file) with the
command you ran, the organization name, and a screenshot of the bot's reply.
