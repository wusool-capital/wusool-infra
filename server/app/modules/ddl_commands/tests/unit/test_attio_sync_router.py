import hashlib
import hmac

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.attio import WebhookEvent, WebhookEventId
from app.modules.ddl_commands.api import attio_sync as router_module

_SECRET = "test-webhook-secret"  # matches conftest.py's ATTIO_WEBHOOK_SECRET default


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(router_module.router)
    return TestClient(app)


def _signed(body: bytes, secret: str = _SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_valid_signature_acks_200_and_dispatches(monkeypatch) -> None:
    """Real confirmed shape (2026-08-18): every delivery is an envelope
    `{"webhook_id": ..., "events": [...]}`, not a bare event object."""
    calls = []

    async def fake_dispatch(upsert, registry, client, event):
        calls.append(event)

    monkeypatch.setattr(router_module, "dispatch_event", fake_dispatch)
    body = (
        b'{"webhook_id": "wh-1", "events": '
        b'[{"event_type": "record.created", "id": {"object_id": "o1", "record_id": "r1"}}]}'
    )

    response = _make_client().post(
        "/webhooks/attio", content=body, headers={"Attio-Signature": _signed(body)}
    )

    assert response.status_code == 200
    assert calls == [
        WebhookEvent(
            event_type="record.created",
            id=WebhookEventId(object_id="o1", record_id="r1"),
        )
    ]


def test_multiple_events_in_one_envelope_all_dispatch(monkeypatch) -> None:
    """`events` is a genuine array -- one delivery can carry more than one
    event, and every one of them must be dispatched, not just the first."""
    calls = []

    async def fake_dispatch(upsert, registry, client, event):
        calls.append(event.id.record_id)

    monkeypatch.setattr(router_module, "dispatch_event", fake_dispatch)
    body = (
        b'{"webhook_id": "wh-1", "events": ['
        b'{"event_type": "record.created", "id": {"object_id": "o1", "record_id": "r1"}},'
        b'{"event_type": "record.updated", "id": {"object_id": "o1", "record_id": "r2"}}'
        b"]}"
    )

    response = _make_client().post(
        "/webhooks/attio", content=body, headers={"Attio-Signature": _signed(body)}
    )

    assert response.status_code == 200
    assert calls == ["r1", "r2"]


def test_empty_events_array_is_a_noop() -> None:
    body = b'{"webhook_id": "wh-1", "events": []}'

    response = _make_client().post(
        "/webhooks/attio", content=body, headers={"Attio-Signature": _signed(body)}
    )

    assert response.status_code == 200


def test_invalid_signature_is_rejected_before_dispatch(monkeypatch) -> None:
    calls = []

    async def fake_dispatch(upsert, registry, client, event):
        calls.append(event)

    monkeypatch.setattr(router_module, "dispatch_event", fake_dispatch)
    body = b'{"webhook_id": "wh-1", "events": [{"event_type": "record.created", "id": {}}]}'

    response = _make_client().post(
        "/webhooks/attio", content=body, headers={"Attio-Signature": "not-the-real-signature"}
    )

    assert response.status_code == 401
    assert calls == []  # rejected before any Attio call or DB write could happen


def test_missing_signature_header_is_rejected() -> None:
    body = b'{"webhook_id": "wh-1", "events": [{"event_type": "record.created", "id": {}}]}'

    response = _make_client().post("/webhooks/attio", content=body)

    assert response.status_code == 401


def test_dispatch_failure_still_returns_200_not_500(monkeypatch) -> None:
    """A bug or a transient Attio/DB failure in our own sync must never
    surface as a failed webhook delivery to Attio, and must never propagate
    into a process-level exception — see router.py's module docstring."""

    async def failing_dispatch(upsert, registry, client, event):
        raise RuntimeError("boom")

    monkeypatch.setattr(router_module, "dispatch_event", failing_dispatch)
    body = (
        b'{"webhook_id": "wh-1", "events": '
        b'[{"event_type": "record.created", "id": {"object_id": "o1", "record_id": "r1"}}]}'
    )

    response = _make_client().post(
        "/webhooks/attio", content=body, headers={"Attio-Signature": _signed(body)}
    )

    assert response.status_code == 200


def test_malformed_json_body_is_rejected(monkeypatch) -> None:
    calls = []

    async def fake_dispatch(upsert, registry, client, event):
        calls.append(event)

    monkeypatch.setattr(router_module, "dispatch_event", fake_dispatch)
    body = b"not valid json"

    response = _make_client().post(
        "/webhooks/attio", content=body, headers={"Attio-Signature": _signed(body)}
    )

    assert response.status_code == 400
    assert calls == []


def test_event_missing_required_field_is_rejected(monkeypatch) -> None:
    """Valid JSON, valid envelope, but one event inside `events` is missing
    its required `event_type` — distinct from the malformed-JSON case
    above, same 400 result."""
    calls = []

    async def fake_dispatch(upsert, registry, client, event):
        calls.append(event)

    monkeypatch.setattr(router_module, "dispatch_event", fake_dispatch)
    body = b'{"webhook_id": "wh-1", "events": [{"id": {"object_id": "o1"}}]}'

    response = _make_client().post(
        "/webhooks/attio", content=body, headers={"Attio-Signature": _signed(body)}
    )

    assert response.status_code == 400
    assert calls == []


def test_validation_failure_logs_the_raw_body(monkeypatch, caplog) -> None:
    """The raw body must be logged on a validation failure -- otherwise a
    real schema mismatch (this is literally how the envelope shape itself
    was discovered) is undiagnosable without a code change after the fact."""
    body = b'{"events": "not a list, a string instead"}'

    with caplog.at_level("ERROR", logger="app.modules.ddl_commands.attio_sync"):
        response = _make_client().post(
            "/webhooks/attio", content=body, headers={"Attio-Signature": _signed(body)}
        )

    assert response.status_code == 400
    assert any("not a list, a string instead" in record.message for record in caplog.records)


# ---------------------------------------------------------------------------
# One SOURCE workspace, two environments
# ---------------------------------------------------------------------------


def _envelope(workspace_id: str | None = None) -> bytes:
    ws = f'"workspace_id": "{workspace_id}", ' if workspace_id else ""
    return (
        b'{"webhook_id": "wh-1", "events": [{"event_type": "record.created", "id": {'
        + ws.encode()
        + b'"object_id": "o1", "record_id": "r1"}}]}'
    )


def _post(body: bytes) -> int:
    return (
        _make_client()
        .post("/webhooks/attio", content=body, headers={"Attio-Signature": _signed(body)})
        .status_code
    )


def test_a_test_scoped_instance_acks_but_does_not_dispatch(monkeypatch) -> None:
    """Sync runs only SOURCE -> the prod database. Enforcing that at the
    route means a dev instance can never reconcile `is_active` back into
    Attio, whatever the per-record filter downstream does. 200, not 4xx: a
    rejection status would have Attio disable the subscription."""
    calls: list[object] = []

    async def fake_dispatch(upsert, registry, client, event):
        calls.append(event)

    monkeypatch.setattr(router_module, "dispatch_event", fake_dispatch)
    monkeypatch.setattr(router_module, "attio_is_test", lambda: True)

    assert _post(_envelope()) == 200
    assert calls == []


def test_event_from_an_unexpected_workspace_is_dropped(monkeypatch) -> None:
    calls: list[object] = []

    async def fake_dispatch(upsert, registry, client, event):
        calls.append(event)

    monkeypatch.setattr(router_module, "dispatch_event", fake_dispatch)
    monkeypatch.setattr(
        router_module, "get_attio_settings", lambda: _FakeAttioSettings("ws-expected")
    )

    assert _post(_envelope("ws-other")) == 200
    assert calls == []


def test_event_from_the_expected_workspace_is_dispatched(monkeypatch) -> None:
    calls: list[object] = []

    async def fake_dispatch(upsert, registry, client, event):
        calls.append(event)

    monkeypatch.setattr(router_module, "dispatch_event", fake_dispatch)
    monkeypatch.setattr(
        router_module, "get_attio_settings", lambda: _FakeAttioSettings("ws-expected")
    )

    assert _post(_envelope("ws-expected")) == 200
    assert len(calls) == 1


def test_workspace_check_is_skipped_when_unset(monkeypatch) -> None:
    """Unset must stay a no-op, so nobody's existing deployment breaks."""
    calls: list[object] = []

    async def fake_dispatch(upsert, registry, client, event):
        calls.append(event)

    monkeypatch.setattr(router_module, "dispatch_event", fake_dispatch)
    monkeypatch.setattr(router_module, "get_attio_settings", lambda: _FakeAttioSettings(None))

    assert _post(_envelope("ws-anything")) == 200
    assert len(calls) == 1


class _FakeAttioSettings:
    def __init__(self, attio_workspace_id: str | None) -> None:
        self.attio_workspace_id = attio_workspace_id
