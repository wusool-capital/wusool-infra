"""Implements `application.ports.email.EmailSenderPort` against a plain SES
client -- the email counterpart to `providers/slack/notifier.py`'s
`SlackWebClientNotifier`. Any module can depend on this for out-of-band
outbound email.

`send_email` (like every boto3 call) is synchronous, so it runs on a
worker thread via `asyncio.to_thread` -- the same pattern
`utilities.providers.bedrock.retry.invoke_bedrock_with_retry` uses for the
Bedrock client `meetings` also owns.

SES itself rejects a `Source` address that isn't a verified identity in
this account/region, independent of anything below -- that verification is
an out-of-band AWS console/CLI step, not something this code can satisfy.
"""

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mypy_boto3_ses import SESClient


class SesMailer:
    def __init__(self, client: "SESClient") -> None:
        self._client = client

    async def send(self, *, to: list[str], from_addr: str, subject: str, body: str) -> None:
        def send_email() -> None:
            self._client.send_email(
                Source=from_addr,
                Destination={"ToAddresses": to},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
                },
            )

        await asyncio.to_thread(send_email)
