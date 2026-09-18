"""Implements `application.ports.email.EmailSenderPort` against a plain SES
client -- the email counterpart to `providers/slack/notifier.py`'s
`SlackWebClientNotifier`. Any module can depend on this for out-of-band
outbound email.

`send_email` (like every boto3 call) is synchronous, so it runs on a
worker thread via `asyncio.to_thread`.

Retries a transient failure (throttling, a momentary AWS-side outage, a
dropped connection) up to 3 times with exponential backoff, using the
same generic loop Bedrock's client retries through
(`utilities.domain.retry.retry_with_backoff` -- `utilities` is a
documented full-access module, safe to import directly). Does NOT retry a
permanent failure: `MessageRejected`, an unverified `Source`/recipient
identity, a paused account/configuration set, or a bad parameter will
never succeed on a second attempt, so retrying would only add latency for
no benefit. The retry is entirely this class's own concern -- callers
just `await send(...)` and either it eventually succeeds or raises once
every attempt is exhausted, the same way `BedrockConverseClient.summarize`
hides its own retry from its callers.

SES itself rejects a `Source` address that isn't a verified identity in
this account/region, independent of anything below -- that verification is
an out-of-band AWS console/CLI step, not something this code can satisfy.
"""

import asyncio
import logging
from typing import TYPE_CHECKING

from botocore.exceptions import ClientError, EndpointConnectionError

from app.modules.utilities.domain.retry import retry_with_backoff

if TYPE_CHECKING:
    from mypy_boto3_ses import SESClient

logger = logging.getLogger(__name__)

# SES's own transient error codes -- distinct from Bedrock's
# TRANSIENT_ERROR_CODES (utilities/domain/bedrock.py), a different vendor
# with a different error taxonomy.
_TRANSIENT_ERROR_CODES = frozenset({"Throttling", "ServiceUnavailable", "InternalFailure"})

_MAX_ATTEMPTS = 3
_BASE_DELAY_SECONDS = 1.0


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, EndpointConnectionError):
        return True
    if isinstance(exc, ClientError):
        return exc.response.get("Error", {}).get("Code", "") in _TRANSIENT_ERROR_CODES
    return False


class SesMailer:
    def __init__(self, client: "SESClient") -> None:
        self._client = client

    async def send(
        self, *, to: list[str], from_addr: str, subject: str, body: str, is_html: bool = False
    ) -> None:
        def send_email() -> None:
            body_key = "Html" if is_html else "Text"
            self._client.send_email(
                Source=from_addr,
                Destination={"ToAddresses": to},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {body_key: {"Data": body, "Charset": "UTF-8"}},
                },
            )

        def on_retry(attempt: int, exc: Exception, delay: float) -> None:
            error_code = (
                exc.response.get("Error", {}).get("Code", "")
                if isinstance(exc, ClientError)
                else "EndpointConnectionError"
            )
            logger.warning(
                "ses_send_failed attempt=%d error_code=%s",
                attempt,
                error_code,
                extra={"attempt": attempt, "error_code": error_code},
            )

        await retry_with_backoff(
            lambda: asyncio.to_thread(send_email),
            is_retryable=_is_retryable,
            max_attempts=_MAX_ATTEMPTS,
            delay_seconds=lambda attempt: _BASE_DELAY_SECONDS * (2 ** (attempt - 1)),
            on_retry=on_retry,
        )
