# Rules and limitations

- **Attio is written first.** Every `/edit-*` and `/add-*` change lands in
  Attio before the database. This keeps the scheduled Attio → database sync
  from overwriting your change.
- **A record you create by hand in Attio counts as real.** It syncs to the
  database the same as anything created through the bot.
- **There is no `/remove-seller` or `/remove-buyer`.** Removing a role is not
  done through the bot.
- **Anyone in the workspace can run these commands.** There is no
  per-user permission list.
- **Two people adding the same organization at the same time** can each
  succeed and create a duplicate. Coordinate before bulk-adding.
