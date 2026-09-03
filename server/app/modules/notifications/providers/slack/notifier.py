"""Implements `application.ports.slack.SlackNotifierPort` against a plain
`AsyncWebClient` — no Bolt `AsyncApp`, no handler registration. Any module
can depend on this for out-of-band outbound Slack messaging; Protocols are
structural, so this one concrete class satisfies every module's own
independently-declared `SlackNotifierPort` with no cross-module import.
"""

from slack_sdk.web.async_client import AsyncWebClient


class SlackWebClientNotifier:
    def __init__(self, client: AsyncWebClient) -> None:
        self._client = client

    async def post_message(
        self, *, channel: str, text: str, blocks: list[dict] | None = None
    ) -> str:
        response = await self._client.chat_postMessage(channel=channel, text=text, blocks=blocks)
        return response["ts"]

    async def update_message(
        self, *, channel: str, ts: str, text: str, blocks: list[dict] | None = None
    ) -> None:
        await self._client.chat_update(channel=channel, ts=ts, text=text, blocks=blocks)

    async def open_view(self, *, trigger_id: str, view: dict) -> None:
        await self._client.views_open(trigger_id=trigger_id, view=view)
