"""HMAC signing for the MCP's stateless OAuth artifacts. The purpose is part of the
signature, so a refresh token can never pass as an access token or a code."""

import base64
import hashlib
import hmac


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _signature(purpose: str, body: str, key: bytes) -> str:
    return _b64(hmac.new(key, f"{purpose}.{body}".encode(), hashlib.sha256).digest())


def sign(payload: bytes, *, purpose: str, key: bytes) -> str:
    body = _b64(payload)
    return f"{body}.{_signature(purpose, body, key)}"


def unsign(token: str, *, purpose: str, key: bytes) -> bytes | None:
    """None for anything tampered with, malformed, or signed for another purpose."""
    body, _, signature = token.partition(".")
    if not body or not hmac.compare_digest(signature, _signature(purpose, body, key)):
        return None
    try:
        return _unb64(body)
    except ValueError:
        return None


def derive(value: str, *, purpose: str, key: bytes) -> str:
    """A secret only this server can recompute, such as a client's secret from its id."""
    return _signature(purpose, value, key)
