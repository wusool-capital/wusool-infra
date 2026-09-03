"""Generic Slack Bolt app construction, shared by every module that runs its
own standalone `AsyncApp` (each module's own `api/slack/bolt_app.py` calls
this rather than duplicating the same three lines). Not built at import
time — the caller decides when/whether to construct it (e.g. behind an
`lru_cache`d factory), so the rest of the application can be imported/tested
without Slack credentials present.
"""

from collections.abc import Callable

from slack_bolt.async_app import AsyncApp


def build_bolt_app(
    bot_token: str, signing_secret: str, register_fn: Callable[[AsyncApp], None]
) -> AsyncApp:
    app = AsyncApp(token=bot_token, signing_secret=signing_secret)
    register_fn(app)
    return app
