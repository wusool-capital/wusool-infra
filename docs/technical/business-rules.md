# Business rules

- **Attio-first writes.** `/edit-*` and `/add-*` write to Attio before the
  database, so the scheduled resync converges instead of overwriting a
  bot-originated change. Partial-write failures report exactly what landed
  and what didn't.
- **Schema authority is the data engineering team, not the bot.** The bot
  never creates or alters a table on its own initiative — every schema
  change goes through a reviewed migration.
- **Not every column is Slack-editable.** System-managed values, pipeline
  scores, and fields that need sign-off before they can be changed from
  Slack are intentionally excluded from the edit forms. See the user
  guide's [Fields you cannot edit from Slack](../user-guide/toolkit/edit-profile.md#fields-you-cannot-edit-from-slack).
- **Every meeting produces a CRM note**, whether or not it resolved to an
  organization — an org-less meeting still files a note, tagged by its
  role (buyer/seller/investor/internal/general), so it stays findable
  without needing an organization to anchor it.
- **Enrichment never writes on its own.** `/enrich-seller`/`/enrich-buyer`
  only ever propose values for review — every save still goes through the
  ordinary `/edit-*` write path (Attio first, then the database).
