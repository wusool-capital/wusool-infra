"""Slack Bolt app construction.

Construction is deferred behind a cached factory (not built at import time)
so the rest of the application can be imported/tested without Slack
credentials present.
"""

from functools import lru_cache

from slack_bolt.async_app import AsyncApp

from app.modules.matching_engine.api.slack.handlers import register_handlers
from app.modules.matching_engine.config import get_settings
from app.modules.notifications import build_bolt_app


@lru_cache
def get_bolt_app() -> AsyncApp:
    settings = get_settings()
    return build_bolt_app(
        settings.slack_bot_token, settings.slack_signing_secret, register_handlers
    )
