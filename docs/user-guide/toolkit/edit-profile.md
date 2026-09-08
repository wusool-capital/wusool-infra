# Editing a profile — `/edit-seller` and `/edit-buyer`

1. Run `/edit-seller <name>` or `/edit-buyer <name>`. Pick the right record
   if the name is ambiguous.
2. **Choose the fields to change.** A form lists the editable fields, grouped
   into *Organization* and *Seller/Buyer profile*. Tick only what you need.
3. **Edit the values.** The next form shows just those fields, pre-filled
   with their current values.
4. **Submit.** The bot writes to Attio first, then the database. If a write
   fails partway, the confirmation message tells you exactly what was saved
   and what was not.

![The field picker modal, grouped into Organization and Seller/Buyer profile.](../../images/toolkit-edit-field-picker.png)

![The edit form, pre-filled with the record's current values.](../../images/toolkit-edit-form.png)

## Fields you cannot edit from Slack

Some fields are intentionally left out of the edit form:

- System-managed values such as an organization's connection strength.
- Scores and enrichment fields (readiness score, lead-quality score, deals
  introduced / converted) — these are set by other processes and need
  sign-off before they can be edited here.
- People/user references such as an organization's owner or a buyer's key
  contact — there is no person picker in the form yet.
- `Intake source` can be changed, but only after ticking the "this is a
  correction" box.
