"""Slack command/action/view handlers, thin adapters over application services.

`register_handlers` is the single registration point the Bolt app calls at
construction time.
"""

from slack_bolt.async_app import AsyncApp

from app.modules.slack.handlers import actions, commands


def register_handlers(app: AsyncApp) -> None:
    commands.register(app)
    actions.register(app)
