# Adding a buyer or seller — `/add-seller` and `/add-buyer`

1. Run `/add-seller <organization name>` or `/add-buyer <organization name>`.
2. **Pick the organization.** If similar organizations already exist, choose
   one to attach the new role to, or choose "create new". If the organization
   you pick already has that role, the bot stops and points you to
   [`/edit-*`](edit-profile.md) instead.
3. **Fill in the form.** Every field is optional except the name of a brand
   new organization. If you are creating a new organization that looks like a
   duplicate, the form warns you but still lets you continue.
4. **Submit.** The bot creates the organization (if new) and the role in
   Attio first, then the database.

