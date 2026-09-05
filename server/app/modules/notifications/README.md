# notifications

Slack-specific infra shared by both `matching_engine` and `ddl_commands`:
out-of-band outbound messaging, and generic Bolt `AsyncApp` construction. No
`api/`, no `bootstrap.py` — this is a peer module other modules call into
directly, not a deployable app of its own.

**Not for in-request replies.** A Slack command/action/view-submission
handler already has Bolt's own injected `client`/`ack`/`respond` — use
those directly inside the handler. Reach for `SlackNotifierPort` only when
posting happens outside that request context (e.g. a background task
finishing a match run and posting the result).

## Structure

_New to this codebase's layering? See [the modular monolith guide](../../../../docs/dev/MODULAR_MONOLITH_GUIDE.md)._

```
notifications/
  __init__.py                        # __all__ — see "Public contract" below
  domain/
    slack_payloads.py                  # TypedDicts for Bolt's inbound command/interaction
                                          # payloads — every handler narrows Bolt's untyped
                                          # dict to these at the boundary
    text.py                             # sanitize_mrkdwn — Slack mrkdwn text escaping
  application/ports/slack.py         # SlackNotifierPort Protocol
  providers/slack/
    client.py                          # get_slack_client(bot_token) — one shared AsyncWebClient, lru_cached
    notifier.py                          # SlackWebClientNotifier — implements the Port
    bolt_app.py                          # build_bolt_app(bot_token, signing_secret, register_fn) —
                                            # both modules' own api/slack/bolt_app.py call this instead
                                            # of duplicating the same three lines
```

## Public contract

Consumers (`matching_engine`, `ddl_commands`) import only from
`app.modules.notifications` — the module's `__all__`:
`SlackNotifierPort`, `SlackWebClientNotifier`, `build_bolt_app`,
`get_slack_client`, `sanitize_mrkdwn`, `SlackCommandPayload`,
`SlackInteractionBody`, `SlackViewSubmissionPayload`. Nobody reaches into
`.providers`/`.application`/`.domain` directly.
`matching_engine/bootstrap.py` constructs the concrete notifier once
(`SlackWebClientNotifier(get_slack_client(bot_token))`) and injects
`SlackNotifierPort` into whatever use case needs to post. Each module's own
`api/slack/bolt_app.py` calls `build_bolt_app` with its own settings and
`register_handlers`.

## Testing

No integration tests of its own — `providers/slack/notifier.py` is
exercised indirectly through `matching_engine`'s own tests (fakes implement
`SlackNotifierPort` there). `tests/test_architecture.py` enforces this
module's own `application/` never imports `providers/`/`fastapi`/
`pydantic`/`sqlalchemy` directly.

## Where to go next

New to this module? See [`HOW-TO-READ.md`](HOW-TO-READ.md).
