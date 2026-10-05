"""Sanity webhook signature check and body shape.

Mirrors `@sanity/webhook`'s `assertValidSignature`: the header is
`t=<ms>,v1=<sig>`, where `sig` is the unpadded base64url HMAC-SHA256 of
`"<t>.<raw body>"`. It must run on the raw bytes; re-encoded JSON can differ.
"""

import base64
import hashlib
import hmac
import re

from pydantic import BaseModel, ConfigDict, Field

SIGNATURE_HEADER = "sanity-webhook-signature"
_HEADER = re.compile(r"^t=(\d+)[, ]+v1=([^, ]+)$")


class SanityWebhookBody(BaseModel):
    """The projection configured on the Sanity webhook (see the module README)."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    slug: str | None = None
    previous_slug: str | None = Field(default=None, alias="previousSlug")


def is_valid_signature(body: bytes, header: str | None, secret: str) -> bool:
    if not header or not secret:
        return False
    match = _HEADER.match(header.strip())
    if match is None:
        return False
    timestamp, signature = match.groups()
    digest = hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).digest()
    expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return hmac.compare_digest(expected, signature)
