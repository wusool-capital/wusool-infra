"""Slack Bolt app construction.

Construction is deferred behind a cached factory (not built at import time)
so the rest of the application can be imported/tested without Slack
credentials present.
"""

from functools import lru_cache

from slack_bolt.async_app import AsyncApp

from app.modules.matching_engine.api.slack.handlers import register_handlers
from app.modules.matching_engine.config import get_settings


@lru_cache
def get_bolt_app() -> AsyncApp:
    settings = get_settings()
    app = AsyncApp(
        token=settings.slack_bot_token,
        signing_secret=settings.slack_signing_secret,
    )
    register_handlers(app)
    return app
