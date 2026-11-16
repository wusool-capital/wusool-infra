"""Implements `DigestPosterPort`: posts the review digest to one Slack channel."""

from app.modules.notifications import SlackNotifierPort, sanitize_mrkdwn


class SlackDigestPoster:
    def __init__(self, notifier: SlackNotifierPort, channel: str) -> None:
        self._notifier = notifier
        self._channel = channel

    async def post(self, text: str) -> None:
        await self._notifier.post_message(channel=self._channel, text=sanitize_mrkdwn(text))
