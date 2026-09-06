# How to read `notifications`

A walkthrough for someone who has never seen this module before. This is a
small module (~200 lines) — you can read every file in it in a few
minutes; this just tells you what order to read them in and the one
concept that actually matters.

## The one-sentence version

This module holds Slack-related code that's generic enough to be shared
by both `matching_engine` and `ddl_commands` — it has no Slack commands of
its own, no database, and nothing that runs standalone. It's a toolbox,
not a service.

## The one thing worth understanding: in-request vs. out-of-band

Slack has two different ways your code ends up talking back to Slack, and
confusing them is the main mistake to avoid in this module's consumers:

- **In-request**: a Slack command/button/modal-submission handler is
  running *right now*, inside a live Slack interaction. Bolt already
  handed that handler a `client`/`ack`/`respond` — **use those directly**,
  not anything in this module.
- **Out-of-band**: something is posting to Slack from OUTSIDE a live
  request — a background task that just finished a long-running match run
  and now needs to post the result, for example. There's no Bolt-injected
  client to reuse here, because there's no request in flight. **This is
  what `SlackNotifierPort` (and `SlackWebClientNotifier`, the thing that
  implements it) is for.**

If you're writing a Slack handler and reaching for something in this
module to reply to the user, you're almost certainly in the wrong place —
go use Bolt's own `respond`/`client` instead.

## A tour of every file

### `application/ports/slack.py` — `SlackNotifierPort`

The interface: `post_message`, `update_message`, `open_view`. Notice it
takes plain `dict`/`Sequence[dict]` for Block Kit content, not
`slack_sdk`'s own `Block`/`View` classes — a Port that other modules
depend on shouldn't force them to import a vendor SDK type just to call
it.

### `providers/slack/notifier.py` — `SlackWebClientNotifier`

The one concrete implementation of that Port, built on a plain
`AsyncWebClient` (no Bolt `AsyncApp`, no handler registration — it doesn't
need either, since it's only ever posting, never receiving).

### `providers/slack/client.py` — `get_slack_client`

Where that `AsyncWebClient` actually comes from: one shared, `lru_cache`d
instance per bot token. Deliberately NOT a full Bolt `AsyncApp` — building
one just to reach its `.client` attribute would re-register every Slack
handler for nothing.

### `providers/slack/bolt_app.py` — `build_bolt_app`

A different, much smaller job: the three lines every module's own
`api/slack/bolt_app.py` needs to construct its actual `AsyncApp` (the
thing that *does* receive Slack events). Extracted here purely so
`matching_engine` and `ddl_commands` don't each duplicate those three
lines. Not built at import time — the caller decides when, typically
behind its own `lru_cache`d factory, so importing this module never
requires real Slack credentials to be present.

### `domain/slack_payloads.py` — the inbound payload shapes

Bolt hands every handler an untyped `dict` for the raw Slack payload
(`SlackCommandPayload` for a slash command, `SlackInteractionBody` for a
button click or view submission). These `TypedDict`s are what every
handler across both bot modules narrows that `dict` into at the boundary,
so the rest of the handler works with named fields instead of `.get()`
calls. Only the keys this codebase actually reads are declared — Slack's
real payloads carry more.

### `domain/text.py` — `sanitize_mrkdwn`

One small, self-contained function: makes arbitrary text safe to embed in
a Slack `mrkdwn` block (Slack doesn't render Markdown headings, uses `~`
for strikethrough instead of `*`, and reserves `&`/`<`/`>` for its own
syntax). Framework-free — it's genuinely Slack-format-specific, not a
generic string-sanitizing primitive, which is why it lives in `domain/`
rather than `utilities`.

## Where to go next

- Posting something from a background task (not a live Slack request) →
  `SlackNotifierPort` + `SlackWebClientNotifier`.
- Building a new module's own Bolt app → `build_bolt_app`, and look at
  how `matching_engine`'s or `ddl_commands`' own
  `api/slack/bolt_app.py` calls it.
- Reading a Slack payload's fields safely → `domain/slack_payloads.py`.
- Everything this module exports is listed in `README.md`'s "Public
  contract" — that list IS the module's `__init__.py` `__all__`, not an
  approximation of it.
