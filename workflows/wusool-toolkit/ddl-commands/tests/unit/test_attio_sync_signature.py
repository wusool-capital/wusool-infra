import hashlib
import hmac

from ddl_commands.shared.attio.signature import verify_attio_signature


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_valid_signature_passes() -> None:
    body = b'{"event_type": "record.created"}'
    secret = "whsec_test"
    assert verify_attio_signature(body, _sign(body, secret), secret) is True


def test_wrong_secret_fails() -> None:
    body = b'{"event_type": "record.created"}'
    assert verify_attio_signature(body, _sign(body, "whsec_test"), "whsec_other") is False


def test_tampered_body_fails() -> None:
    secret = "whsec_test"
    signature = _sign(b'{"event_type": "record.created"}', secret)
    assert verify_attio_signature(b'{"event_type": "record.deleted"}', signature, secret) is False


def test_missing_header_fails() -> None:
    body = b'{"event_type": "record.created"}'
    assert verify_attio_signature(body, None, "whsec_test") is False


def test_empty_header_fails() -> None:
    body = b'{"event_type": "record.created"}'
    assert verify_attio_signature(body, "", "whsec_test") is False
