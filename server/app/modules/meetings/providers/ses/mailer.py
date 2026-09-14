"""Real AWS SES implementation of `EmailSenderPort`. `send_email` (like
every boto3 call) is synchronous, so it runs on a worker thread via
`asyncio.to_thread` -- the same pattern
`utilities.providers.bedrock.retry.invoke_bedrock_with_retry` uses for the
Bedrock client this module also owns.

SES itself rejects a `Source` address that isn't a verified identity in
this account/region, independent of anything below -- that verification is
an out-of-band AWS console/CLI step, not something this code can satisfy.
"""

import asyncio

from app.modules.meetings.providers.ses.boto_client import get_ses_client


class SesMailer:
    def __init__(self) -> None:
        self._client = get_ses_client()

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
