# Known limitations

## Wusool Toolkit (Slack bot)

- No per-user authorization — any workspace member can run any command.
- No `/remove-seller` / `/remove-buyer` — this was built once and
  deliberately reverted; removing a role is not currently supported through
  the bot.
- Two `/add-*` submissions for the same organization at the same moment can
  both succeed and create a duplicate — there is no cross-request lock for
  this case.
- Runs as a single process, so it does not currently support running more
  than one instance at once.

## Matching engine

- The web-search fallback is limited to Google-Maps leads, and results are
  never persisted.
- No semantic/vector retrieval, document ingestion, seller-financial
  enrichment, PDF generation, or outreach — these are out of scope by
  design, not oversights.

## Infrastructure

- **No manual approval gate** exists before a production deploy — a
  deliberate, accepted trade-off given the automatic health checks in
  place.
- **AWS SES is in sandbox mode** — each recipient email address must be
  individually verified before it can receive n8n email. This is a
  one-time setup step per recipient, not an ongoing limitation.
- {% hint style="warning" %}Verify before delivery{% endhint %} The
  production n8n bootstrap procedure may lag the current infrastructure
  template — confirm before relying on it for an emergency re-provision.
