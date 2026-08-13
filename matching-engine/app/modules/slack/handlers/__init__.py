"""Slack command/action/view handlers, thin adapters over application services.

`register_handlers` is the single registration point the Bolt app calls at
construction time. Individual handlers (`/find-match`, buyer disambiguation,
approve/reject) are registered here as they're implemented — none are yet;
that's the workflow this module boundary exists to receive.
"""

from slack_bolt.async_app import AsyncApp


def register_handlers(app: AsyncApp) -> None:
    pass
