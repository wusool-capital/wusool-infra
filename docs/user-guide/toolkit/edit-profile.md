# Editing a profile — `/edit-seller` and `/edit-buyer`

1. Run `/edit-seller <name>` or `/edit-buyer <name>`. Pick the right record
   if the name is ambiguous.
2. **Choose the fields to change.** A form lists the editable fields, grouped
   into *Organization* and *Seller/Buyer profile*. Tick only what you need.
3. **Edit the values.** The next form shows just those fields, pre-filled
   with their current values.
4. **Save.** The bot writes to Attio first, then the database. If a write
   fails partway, the confirmation message tells you exactly what was saved
   and what was not.

## Example walkthrough

You run:

> `/edit-seller Al Noor Manufacturing`

The name matches exactly one seller, so the bot opens a field picker
listing the editable *Organization* and *Seller profile* fields. You tick
**HQ country** and **Employee range**, then press **Continue**.

The next form shows just those two fields, pre-filled with their current
values (blank, if they were never set). You enter:

- **HQ country:** United Arab Emirates
- **Employee range:** 51-250

Then press **Save**. The bot writes both fields to Attio, then to the
database, and posts:

> *Updated* seller profile for *Al Noor Manufacturing*.

After a successful buyer edit, the confirmation message suggests a
copy-pasteable `/find-match <name>` command — a convenient next step if you
just updated the buyer's requirements and want to see matches right away.
If a profile still has empty fields, [`/enrich-seller`/`/enrich-buyer`](enrich.md)
can propose values for you to review instead of filling them in by hand.

## Fields you cannot edit from Slack

Some fields are intentionally left out of the edit form:

- System-managed values such as an organization's connection strength.
- Scores and pipeline fields set by other processes (readiness score,
  lead-quality score, deals introduced / converted) — not to be confused
  with the fields [`/enrich-seller`/`/enrich-buyer`](enrich.md) can propose
  values for, which *are* editable here. These need sign-off before they
  can be changed from Slack.
- People/user references such as an organization's owner or a buyer's key
  contact — there is no person picker in the form yet.
- `Intake source` can be changed, but only after ticking the "this is a
  correction" box.
