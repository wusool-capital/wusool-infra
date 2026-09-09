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

- **The toolkit bot's EC2 instance self-heals but does not fail over.** It
  runs in an Auto Scaling Group of size 1, so a terminated or
  hardware-impaired instance is replaced automatically (the Elastic IP
  re-associates itself, so the public URL never changes), and the app
  container is restarted automatically if it stops responding to its health
  check. None of this is zero-downtime — there is still a gap of a few
  minutes while a replacement instance boots, because the bot still runs as
  a single process (see the limitation above) and cannot yet run two
  instances at once.
- A separate Route 53 health check watches the bot from outside AWS's
  network and alerts (email, via the existing infrastructure alerts topic)
  on a pure connectivity gap — it does not auto-recover anything, it exists
  so that failure mode is visible instead of silent.
- **No manual approval gate** exists before a production deploy — a
  deliberate, accepted trade-off given the automatic health checks in
  place.
- **AWS SES is in sandbox mode** — each recipient email address must be
  individually verified before it can receive n8n email. This is a
  one-time setup step per recipient, not an ongoing limitation.
- The production n8n bootstrap procedure may lag the current infrastructure
  template — confirm before relying on it for an emergency re-provision.
