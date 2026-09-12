# Adding a buyer or seller — `/add-seller` and `/add-buyer`

1. Run `/add-seller <organization name>` or `/add-buyer <organization name>`.
2. **Pick the organization.** If similar organizations already exist, choose
   one to attach the new role to, or choose "create new". If the organization
   you pick already has that role, the bot stops and points you to
   [`/edit-*`](edit-profile.md) instead.
3. **Fill in the form.** Every field is optional except the name of a brand
   new organization. If you are creating a new organization that looks like a
   duplicate, the form warns you but still lets you continue.
4. **Save.** The bot creates the organization (if new) and the role in
   Attio first, then the database.

## Example walkthrough

You run:

> `/add-buyer Raoof Capital`

No existing organization matches closely enough, so the bot offers
**"None of these — create new organization"** alongside any near-matches.
You pick that option and press **Continue**.

The add form opens. Name is the only required field, so you leave
everything else blank for now and press **Save**.

The bot creates the organization and the buyer role in Attio, then in the
database, and posts:

> *Added* buyer profile for *Raoof Capital*.

You can now run `/find-match Raoof Capital` once the profile has enough
detail to compare against sellers, or
[`/enrich-buyer Raoof Capital`](enrich.md) first if it's missing fields.

For a new seller, the confirmation message suggests a copy-pasteable
`/enrich-seller <name>` command instead — a newly-added record is usually
the one most worth researching for missing details. See
[Filling in missing details](enrich.md).
