"""The Slack-notification interface any module can depend on for out-of-band
outbound messaging (no live Slack request in flight) — implemented by
`providers/slack/notifier.py`. Not for in-request replies: Bolt's own
injected `client`/`ack`/`respond` already cover those (see this module's
README for the inbound-vs-outbound-vs-in-request distinction).
"""

from typing import Protocol


class SlackNotifierPort(Protocol):
    async def post_message(
        self, *, channel: str, text: str, blocks: list[dict] | None = None
    ) -> str:
        """Returns the posted message's `ts`, so a caller can `update_message` it later."""
        ...

    async def update_message(
        self, *, channel: str, ts: str, text: str, blocks: list[dict] | None = None
    ) -> None: ...

    async def open_view(self, *, trigger_id: str, view: dict) -> None: ...
