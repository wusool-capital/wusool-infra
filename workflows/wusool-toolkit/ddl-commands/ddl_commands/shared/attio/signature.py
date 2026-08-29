"""Verifies inbound Attio webhook deliveries are genuinely from Attio.

Attio signs the raw request body with HMAC-SHA256, keyed by the secret
handed back exactly once in the response to `POST /v2/webhooks` (never
retrievable again after that), and sends the hex digest in the
`Attio-Signature` header. `hmac.compare_digest` is used instead of `==` so a
forged request can't learn how much of the signature it got right from
response timing.
"""

import hashlib
import hmac


def verify_attio_signature(raw_body: bytes, signature_header: str | None, secret: str) -> bool:
    if not signature_header:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)
