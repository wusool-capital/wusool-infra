# Creating contacts from email

How the interactions engine turns an unknown outside address into a Person and an Organization in Attio. See [Interactions engine](interactions.md) for the rest of the engine and its settings.

It has been on in production since 16 November, creating at most 20 Persons per round.

## Who qualifies

When an outside address has no Person, the engine can create one. It needs a two-way thread or a meeting that wasn't cancelled. Internal, free-email, no-reply, help, invite, support, and bulk senders never qualify.

It creates the Organization first, unless the domain has one, then the Person linked to it. Both are tagged Lead Source Detail "Email sync". The Person's name is the sender's display name, or the address when there is none.

Postgres lags the webhook, so the engine records each create and asks Attio whether the email exists before creating. An address or domain that matches several records creates nothing. It is saved for review, and new cases are posted to Slack once a day. A case resolves itself once it is fixed.

## Settings

`INTERACTIONS_AUTO_CREATE_MODE` is `off` by default, and `dry_run` logs counts only. `INTERACTIONS_AUTO_CREATE_MAX_PER_ROUND` caps the Persons created in one round. `INTERACTIONS_REVIEW_SLACK_CHANNEL` is the channel for the daily review post; empty turns it off.

The engine refuses to create anything while `ATTIO_IS_TEST` is set. A created record can only be undone in Attio. The steps for turning it on are in the Google access runbook, `docs/runbooks/google-delegation.md`.
