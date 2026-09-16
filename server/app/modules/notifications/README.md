# notifications

Out-of-band outbound messaging infra shared across modules: Slack (plus
generic Bolt `AsyncApp` construction) and email via SES. No `api/`, no
`bootstrap.py` — this is a peer module other modules call into directly,
not a deployable app of its own.

**Not for in-request Slack replies.** A Slack command/action/view-
submission handler already has Bolt's own injected `client`/`ack`/
`respond` — use those directly inside the handler. Reach for
`SlackNotifierPort` only when posting happens outside that request context
(e.g. a background task finishing a match run and posting the result).
Email has no in-request counterpart — `EmailSenderPort` is always the
right thing. `send`'s `is_html` flag (default `False`) picks `Body.Html`
over `Body.Text` on the underlying SES call — added for `lead_magnets`'
HTML confirmation/internal-notice emails; `meetings`' plain-text feedback
email is unaffected by the default.

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
  application/ports/
    slack.py                           # SlackNotifierPort Protocol
    email.py                           # EmailSenderPort Protocol
  providers/
    slack/
      client.py                          # get_slack_client(bot_token) — one shared AsyncWebClient, lru_cached
      notifier.py                          # SlackWebClientNotifier — implements SlackNotifierPort
      bolt_app.py                          # build_bolt_app(bot_token, signing_secret, register_fn) —
                                              # both modules' own api/slack/bolt_app.py call this instead
                                              # of duplicating the same three lines
    ses/
      client.py                          # get_ses_client(region_name, ...) — one shared SES client, lru_cached
      mailer.py                            # SesMailer — implements EmailSenderPort
```

## Public contract

Consumers (`matching_engine`, `ddl_commands`, `enrichment`, `discovery`,
`meetings`, `lead_magnets`) import only from `app.modules.notifications` — the module's
`__all__`: `SlackNotifierPort`, `SlackWebClientNotifier`, `build_bolt_app`,
`get_slack_client`, `sanitize_mrkdwn`, `SlackCommandPayload`,
`SlackInteractionBody`, `SlackViewSubmissionPayload`, `EmailSenderPort`,
`SesMailer`, `get_ses_client`. Nobody reaches into `.providers`/
`.application`/`.domain` directly.

`matching_engine/bootstrap.py` constructs the concrete Slack notifier once
(`SlackWebClientNotifier(get_slack_client(bot_token))`) and injects
`SlackNotifierPort` into whatever use case needs to post. Each module's own
`api/slack/bolt_app.py` calls `build_bolt_app` with its own settings and
`register_handlers`. `meetings/bootstrap.py::build_feedback_mailer`
constructs the email counterpart the same way
(`SesMailer(get_ses_client(region_name=..., aws_access_key_id=..., aws_secret_access_key=...))`),
consumed by `api/dependencies.py::feedback_mailer` and injected as
`EmailSenderPort` — matching this module's own rule (see
`bootstrap.py`'s docstring) that concrete provider construction belongs
in `bootstrap.py`, not inline in `api/dependencies.py`.
`lead_magnets/bootstrap.py::build_lead_magnet_mailer` does the same,
minus explicit AWS keys (that module's own `Settings` has none — see its
docstring), injected into `SubmissionService` for the confirmation/
internal-notice emails.

Neither `get_slack_client` nor `get_ses_client` reads any module's
`Settings` — every credential is a parameter, so this module has zero
config of its own; each caller supplies its own bot token / AWS
credentials.

## Testing

No integration tests of its own — `providers/slack/notifier.py` and
`providers/ses/mailer.py` are exercised indirectly through their
consumers' own tests (fakes implement `SlackNotifierPort`/
`EmailSenderPort` there — see `meetings/tests/integration/
test_feedback_api.py`'s `_FakeMailer`). `tests/test_architecture.py`
enforces this module's own `application/` never imports `providers/`/
`fastapi`/`pydantic`/`sqlalchemy` directly.

## Where to go next

New to this module? See [`HOW-TO-READ.md`](HOW-TO-READ.md).
