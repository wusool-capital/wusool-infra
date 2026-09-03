# notifications

Out-of-band outbound Slack messaging — posting/updating a message or
opening a view **when there's no live Bolt request in flight** (e.g. a
background task finishing a match run and posting the result). No `api/`,
no `bootstrap.py` — this is a peer module other modules call into directly,
not a deployable app of its own.

**Not for in-request replies.** A Slack command/action/view-submission
handler already has Bolt's own injected `client`/`ack`/`respond` — use
those directly inside the handler. Reach for this module only when posting
happens outside that request context.

## Structure

```
notifications/
  __init__.py                        # __all__: SlackNotifierPort, SlackWebClientNotifier, get_slack_client
  application/ports/slack.py         # SlackNotifierPort Protocol
  providers/slack/
    client.py                          # get_slack_client(bot_token) — one shared AsyncWebClient, lru_cached
    notifier.py                          # SlackWebClientNotifier — implements the Port
```

## Public contract

Consumers (`matching_engine`) import only `from app.modules.notifications
import SlackNotifierPort, SlackWebClientNotifier, get_slack_client` — the
module's `__all__`. `matching_engine/bootstrap.py` constructs the concrete
notifier once (`SlackWebClientNotifier(get_slack_client(bot_token))`) and
injects `SlackNotifierPort` into whatever use case needs to post.

## Testing

No integration tests of its own — `providers/slack/notifier.py` is
exercised indirectly through `matching_engine`'s own tests (fakes implement
`SlackNotifierPort` there). `tests/test_architecture.py` enforces this
module's own `application/` never imports `providers/`/`fastapi`/
`pydantic`/`sqlalchemy` directly.
