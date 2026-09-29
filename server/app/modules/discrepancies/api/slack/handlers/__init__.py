from slack_bolt.async_app import AsyncApp

from app.modules.discrepancies.api.slack.handlers import actions, commands


def register_handlers(app: AsyncApp) -> None:
    commands.register(app)
    actions.register(app)
