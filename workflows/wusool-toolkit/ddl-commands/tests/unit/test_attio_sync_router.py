import hashlib
import hmac

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ddl_commands.modules.attio_sync import router as router_module
from ddl_commands.modules.attio_sync.schemas import AttioWebhookEvent, AttioWebhookEventId

_SECRET = "test-webhook-secret"  # matches conftest.py's ATTIO_WEBHOOK_SECRET default


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(router_module.router)
    return TestClient(app)


def _signed(body: bytes, secret: str = _SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_valid_signature_acks_200_and_dispatches(monkeypatch) -> None:
    calls = []

    async def fake_dispatch(client, event):
        calls.append(event)

    monkeypatch.setattr(router_module, "dispatch_event", fake_dispatch)
    body = b'{"event_type": "record.created", "id": {"object_id": "o1", "record_id": "r1"}}'

    response = _make_client().post(
        "/webhooks/attio", content=body, headers={"Attio-Signature": _signed(body)}
    )

    assert response.status_code == 200
    assert calls == [
        AttioWebhookEvent(
            event_type="record.created",
            id=AttioWebhookEventId(object_id="o1", record_id="r1"),
        )
    ]


def test_invalid_signature_is_rejected_before_dispatch(monkeypatch) -> None:
    calls = []

    async def fake_dispatch(client, event):
        calls.append(event)

    monkeypatch.setattr(router_module, "dispatch_event", fake_dispatch)
    body = b'{"event_type": "record.created", "id": {}}'

    response = _make_client().post(
        "/webhooks/attio", content=body, headers={"Attio-Signature": "not-the-real-signature"}
    )

    assert response.status_code == 401
    assert calls == []  # rejected before any Attio call or DB write could happen


def test_missing_signature_header_is_rejected() -> None:
    body = b'{"event_type": "record.created", "id": {}}'

    response = _make_client().post("/webhooks/attio", content=body)

    assert response.status_code == 401


def test_dispatch_failure_still_returns_200_not_500(monkeypatch) -> None:
    """A bug or a transient Attio/DB failure in our own sync must never
    surface as a failed webhook delivery to Attio, and must never propagate
    into a process-level exception — see router.py's module docstring."""

    async def failing_dispatch(client, event):
        raise RuntimeError("boom")

    monkeypatch.setattr(router_module, "dispatch_event", failing_dispatch)
    body = b'{"event_type": "record.created", "id": {"object_id": "o1", "record_id": "r1"}}'

    response = _make_client().post(
        "/webhooks/attio", content=body, headers={"Attio-Signature": _signed(body)}
    )

    assert response.status_code == 200


def test_malformed_json_body_is_rejected(monkeypatch) -> None:
    calls = []

    async def fake_dispatch(client, event):
        calls.append(event)

    monkeypatch.setattr(router_module, "dispatch_event", fake_dispatch)
    body = b"not valid json"

    response = _make_client().post(
        "/webhooks/attio", content=body, headers={"Attio-Signature": _signed(body)}
    )

    assert response.status_code == 400
    assert calls == []


def test_valid_json_missing_required_field_is_rejected(monkeypatch) -> None:
    """Valid JSON, but failing pydantic schema validation (no `event_type`)
    — distinct from the malformed-JSON case above, same 400 result."""
    calls = []

    async def fake_dispatch(client, event):
        calls.append(event)

    monkeypatch.setattr(router_module, "dispatch_event", fake_dispatch)
    body = b'{"id": {"object_id": "o1", "record_id": "r1"}}'

    response = _make_client().post(
        "/webhooks/attio", content=body, headers={"Attio-Signature": _signed(body)}
    )

    assert response.status_code == 400
    assert calls == []
