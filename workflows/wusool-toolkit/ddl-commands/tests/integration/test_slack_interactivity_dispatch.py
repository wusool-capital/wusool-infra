"""End-to-end Slack *interactivity* dispatch — closes the gap between "the
repository/use-case logic is correct" and "the wiring from a real Slack
payload to that logic is correct," across the full 3-step edit flow
(selection -> field-picker -> dynamic form). No live Slack workspace, no
database, no live Attio: every payload is hand-built to match Slack's real
`view_submission` shape, signed with the same HMAC scheme Slack really uses,
and every DB/Attio-touching call is monkeypatched at its import site in
`ddl_commands.modules.slack.handlers.actions` so this file asserts *the
right function got called with the right arguments, in the right order* —
Attio before Postgres, and never Postgres at all if Attio fails.
"""

import hashlib
import hmac
import json
import time
import uuid
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

import ddl_commands.modules.slack.handlers.actions as actions_module
from ddl_commands.config import get_settings
from ddl_commands.main import app
from ddl_commands.modules.slack.views.organization_selection import NEW_ORGANIZATION_VALUE
from ddl_commands.shared.attio.client import AttioError


def _sign(body: str, timestamp: str, signing_secret: str) -> str:
    basestring = f"v0:{timestamp}:{body}".encode()
    digest = hmac.new(signing_secret.encode(), basestring, hashlib.sha256).hexdigest()
    return f"v0={digest}"


def _post_interactivity(payload: dict) -> "TestClient.__class__":
    settings = get_settings()
    body = urlencode({"payload": json.dumps(payload)})
    timestamp = str(int(time.time()))
    signature = _sign(body, timestamp, settings.slack_signing_secret)
    client = TestClient(app)
    return client.post(
        "/slack/events",
        content=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": signature,
        },
    )


def _async_returning(value):
    async def _fn(*_args, **_kwargs):
        return value

    return _fn


def _fake_org(
    attio_id: str = "org-attio-1",
    name: str = "Acme Capital",
    removed_at=None,
    seller_role=None,
    buyer_role=None,
):
    return SimpleNamespace(
        attio_id=attio_id,
        name=name,
        removed_at=removed_at,
        description=None,
        hq_country=None,
        sector_focus=None,
        client_type=None,
        relationship_status=None,
        estimated_arr=None,
        funding_raised=None,
        seller_role=seller_role,
        buyer_role=buyer_role,
    )


def _fake_seller_role(role_id: str, *, org=None):
    return SimpleNamespace(
        id=role_id,
        organization=org or _fake_org(),
        outreach_tier=None,
        appetite_signal=None,
        relationship_status=None,
        sell_timeline=None,
        last_attempt_date=None,
        last_attempt_channel=None,
        last_attempt_outcome=None,
        re_engage_date=None,
        est_revenue=None,
        est_ebitda=None,
        owner_salary=None,
        valuation_low=None,
        valuation_mid=None,
        valuation_high=None,
        intake_source=None,
    )


def _fake_buyer_role(role_id: str, *, org=None):
    return SimpleNamespace(
        id=role_id,
        organization=org or _fake_org(name="Blue Horizon"),
        model=None,
        mandate_status=None,
        deal_structure_tolerance=None,
        earnout_tolerance=None,
        profitable_only=None,
        investment_strategy=None,
        notes=None,
        ebitda_floor=None,
        check_size_min=None,
        check_size_max=None,
        ev_ceiling=None,
    )


@pytest.fixture(autouse=True)
def _mock_slack_web_client(monkeypatch):
    posted: list[dict] = []

    async def fake_chat_post_ephemeral(self, **kwargs):  # noqa: ANN001
        posted.append(kwargs)
        return {"ok": True}

    class _FakeAuthTestResponse(dict):
        headers: dict = {}

    async def fake_auth_test(self, **kwargs):  # noqa: ANN001
        return _FakeAuthTestResponse(ok=True, user_id="U_BOT", team_id="T_TEST", bot_id="B_TEST")

    monkeypatch.setattr(
        "slack_sdk.web.async_client.AsyncWebClient.chat_postEphemeral", fake_chat_post_ephemeral
    )
    monkeypatch.setattr("slack_sdk.web.async_client.AsyncWebClient.auth_test", fake_auth_test)
    return SimpleNamespace(posted=posted)


# --------------------------------------------------------------------------
# Step 1: seller_role_selection_modal / buyer_role_selection_modal -> field-picker
# --------------------------------------------------------------------------


def test_seller_selection_opens_field_picker(monkeypatch) -> None:
    seller_id = str(uuid.uuid4())
    monkeypatch.setattr(
        actions_module,
        "resolve_seller_by_id",
        _async_returning(_fake_seller_role(seller_id, org=_fake_org(name="Typo Target Co"))),
    )

    payload = {
        "type": "view_submission",
        "user": {"id": "U_TEST"},
        "view": {
            "type": "modal",
            "id": "V1",
            "callback_id": "seller_role_selection_modal",
            "private_metadata": json.dumps({"requested_by": "U_TEST", "channel_id": "C_TEST"}),
            "state": {
                "values": {
                    "seller_role_id": {
                        "selected_seller": {"selected_option": {"value": seller_id}}
                    }
                }
            },
        },
    }

    response = _post_interactivity(payload)

    assert response.status_code == 200
    body = response.json()
    assert body["response_action"] == "update"
    assert body["view"]["callback_id"] == "seller_field_picker_modal"
    metadata = json.loads(body["view"]["private_metadata"])
    assert metadata["seller_role_id"] == seller_id
    assert metadata["org_name"] == "Typo Target Co"


def test_buyer_selection_opens_field_picker(monkeypatch) -> None:
    buyer_id = str(uuid.uuid4())
    monkeypatch.setattr(
        actions_module,
        "resolve_buyer_by_id",
        _async_returning(_fake_buyer_role(buyer_id, org=_fake_org(name="Blue Horizon Buyers"))),
    )

    payload = {
        "type": "view_submission",
        "user": {"id": "U_TEST"},
        "view": {
            "type": "modal",
            "id": "V1",
            "callback_id": "buyer_role_selection_modal",
            "private_metadata": json.dumps({"requested_by": "U_TEST", "channel_id": "C_TEST"}),
            "state": {
                "values": {
                    "buyer_role_id": {"selected_buyer": {"selected_option": {"value": buyer_id}}}
                }
            },
        },
    }

    response = _post_interactivity(payload)

    assert response.status_code == 200
    body = response.json()
    assert body["response_action"] == "update"
    assert body["view"]["callback_id"] == "buyer_field_picker_modal"
    metadata = json.loads(body["view"]["private_metadata"])
    assert metadata["buyer_role_id"] == buyer_id
    assert metadata["org_name"] == "Blue Horizon Buyers"


# --------------------------------------------------------------------------
# Step 2: field-picker -> dynamic edit form
# --------------------------------------------------------------------------


def test_seller_field_picker_opens_dynamic_form_with_only_selected_fields(monkeypatch) -> None:
    seller_id = str(uuid.uuid4())
    monkeypatch.setattr(
        actions_module, "resolve_seller_by_id", _async_returning(_fake_seller_role(seller_id))
    )

    payload = {
        "type": "view_submission",
        "user": {"id": "U_TEST"},
        "view": {
            "type": "modal",
            "id": "V2",
            "callback_id": "seller_field_picker_modal",
            "private_metadata": json.dumps(
                {
                    "seller_role_id": seller_id,
                    "org_name": "Acme Capital",
                    "requested_by": "U_TEST",
                    "channel_id": "C_TEST",
                }
            ),
            "state": {
                "values": {
                    "org_fields": {
                        "selected_org_fields": {"selected_options": [{"value": "description"}]}
                    },
                    "role_fields": {
                        "selected_role_fields": {"selected_options": [{"value": "outreach_tier"}]}
                    },
                }
            },
        },
    }

    response = _post_interactivity(payload)

    assert response.status_code == 200
    body = response.json()
    assert body["response_action"] == "update"
    assert body["view"]["callback_id"] == "seller_edit_form_modal"
    block_ids = {b["block_id"] for b in body["view"]["blocks"]}
    assert block_ids == {"org_description", "outreach_tier"}
    metadata = json.loads(body["view"]["private_metadata"])
    assert metadata["selected_org_fields"] == ["description"]
    assert metadata["selected_role_fields"] == ["outreach_tier"]


def test_field_picker_with_nothing_selected_shows_usage_error(monkeypatch) -> None:
    seller_id = str(uuid.uuid4())
    monkeypatch.setattr(
        actions_module, "resolve_seller_by_id", _async_returning(_fake_seller_role(seller_id))
    )

    payload = {
        "type": "view_submission",
        "user": {"id": "U_TEST"},
        "view": {
            "type": "modal",
            "id": "V2",
            "callback_id": "seller_field_picker_modal",
            "private_metadata": json.dumps(
                {
                    "seller_role_id": seller_id,
                    "org_name": "Acme Capital",
                    "requested_by": "U_TEST",
                    "channel_id": "C_TEST",
                }
            ),
            "state": {"values": {}},
        },
    }

    response = _post_interactivity(payload)

    assert response.status_code == 200
    assert response.text == ""


# --------------------------------------------------------------------------
# Step 3: dynamic edit form submission -> Attio, then Postgres
# --------------------------------------------------------------------------


def _seller_edit_form_payload(
    seller_id: str, org_attio_id: str, org_fields: list, role_fields: list, values: dict
) -> dict:
    return {
        "type": "view_submission",
        "user": {"id": "U_TEST"},
        "view": {
            "type": "modal",
            "id": "V3",
            "callback_id": "seller_edit_form_modal",
            "private_metadata": json.dumps(
                {
                    "seller_role_id": seller_id,
                    "org_attio_id": org_attio_id,
                    "org_name": "Acme Capital",
                    "requested_by": "U_TEST",
                    "channel_id": "C_TEST",
                    "selected_org_fields": org_fields,
                    "selected_role_fields": role_fields,
                }
            ),
            "state": {"values": values},
        },
    }


def test_edit_form_writes_attio_before_postgres(monkeypatch, _mock_slack_web_client) -> None:
    seller_id = str(uuid.uuid4())
    org = _fake_org(attio_id="org-attio-1")
    monkeypatch.setattr(
        actions_module,
        "resolve_seller_by_id",
        _async_returning(_fake_seller_role(seller_id, org=org)),
    )

    call_order: list[str] = []

    async def fake_build_attio_values(*_args, **_kwargs):
        call_order.append("build_attio_values")
        return {"outreach_tier": "opt-tier-1"}

    async def fake_resolve_role_entry_id(*_args, **_kwargs):
        call_order.append("resolve_role_entry_id")
        return "entry-1"

    async def fake_patch_role_entry(*_args, **_kwargs):
        call_order.append("patch_role_entry")

    postgres_use_case = SimpleNamespace(calls=[])

    async def fake_execute(*args, **kwargs):
        call_order.append("postgres_write")
        postgres_use_case.calls.append((args, kwargs))
        return None

    monkeypatch.setattr(actions_module, "build_attio_values", fake_build_attio_values)
    monkeypatch.setattr(actions_module, "resolve_role_entry_id", fake_resolve_role_entry_id)
    monkeypatch.setattr(actions_module, "patch_role_entry", fake_patch_role_entry)
    monkeypatch.setattr(actions_module, "get_attio_client", lambda: object())
    monkeypatch.setattr(
        actions_module,
        "build_update_seller_use_case",
        lambda: SimpleNamespace(execute=fake_execute),
    )

    values = {"outreach_tier": {"outreach_tier": {"selected_option": {"value": "Tier 1"}}}}
    payload = _seller_edit_form_payload(seller_id, "org-attio-1", [], ["outreach_tier"], values)

    response = _post_interactivity(payload)

    assert response.status_code == 200
    assert response.text == ""
    assert call_order == [
        "build_attio_values",
        "resolve_role_entry_id",
        "patch_role_entry",
        "postgres_write",
    ]
    args, kwargs = postgres_use_case.calls[0]
    assert args[0] == seller_id
    assert kwargs["org_attio_id"] == "org-attio-1"
    assert "Updated seller profile for Acme Capital" in _mock_slack_web_client.posted[0]["text"]


def test_edit_form_attio_failure_prevents_postgres_write(
    monkeypatch, _mock_slack_web_client
) -> None:
    seller_id = str(uuid.uuid4())
    org = _fake_org(attio_id="org-attio-1")
    monkeypatch.setattr(
        actions_module,
        "resolve_seller_by_id",
        _async_returning(_fake_seller_role(seller_id, org=org)),
    )

    from ddl_commands.shared.attio.options import OptionNotFoundError

    async def failing_build_attio_values(*_args, **_kwargs):
        raise OptionNotFoundError("outreach_tier", "lists", "Tier 1")

    postgres_calls: list = []

    async def fake_execute(*args, **kwargs):
        postgres_calls.append((args, kwargs))
        return None

    monkeypatch.setattr(actions_module, "build_attio_values", failing_build_attio_values)
    monkeypatch.setattr(actions_module, "get_attio_client", lambda: object())
    monkeypatch.setattr(
        actions_module,
        "build_update_seller_use_case",
        lambda: SimpleNamespace(execute=fake_execute),
    )

    values = {"outreach_tier": {"outreach_tier": {"selected_option": {"value": "Tier 1"}}}}
    payload = _seller_edit_form_payload(seller_id, "org-attio-1", [], ["outreach_tier"], values)

    response = _post_interactivity(payload)

    assert response.status_code == 200
    assert postgres_calls == []
    assert "Couldn't write to Attio, nothing was saved" in _mock_slack_web_client.posted[0]["text"]


def test_edit_form_org_patch_succeeds_role_patch_fails_reports_what_landed(
    monkeypatch, _mock_slack_web_client
) -> None:
    """Org fields PATCH to Attio successfully, then the role fields PATCH
    fails — Attio now holds a partial edit. The message must say the org
    fields landed, not claim "nothing was saved".
    """
    seller_id = str(uuid.uuid4())
    org = _fake_org(attio_id="org-attio-1")
    monkeypatch.setattr(
        actions_module,
        "resolve_seller_by_id",
        _async_returning(_fake_seller_role(seller_id, org=org)),
    )

    async def fake_build_attio_values(*_args, **_kwargs):
        return {"some": "value"}

    async def fake_patch_organization(*_args, **_kwargs):
        return None

    async def failing_resolve_role_entry_id(*_args, **_kwargs):
        raise AttioError(500, "entry lookup failed")

    postgres_calls: list = []

    async def fake_execute(*args, **kwargs):
        postgres_calls.append((args, kwargs))
        return None

    monkeypatch.setattr(actions_module, "build_attio_values", fake_build_attio_values)
    monkeypatch.setattr(actions_module, "patch_organization", fake_patch_organization)
    monkeypatch.setattr(actions_module, "resolve_role_entry_id", failing_resolve_role_entry_id)
    monkeypatch.setattr(actions_module, "get_attio_client", lambda: object())
    monkeypatch.setattr(
        actions_module,
        "build_update_seller_use_case",
        lambda: SimpleNamespace(execute=fake_execute),
    )

    values = {
        "org_hq_country": {"org_hq_country": {"value": "AE"}},
        "outreach_tier": {"outreach_tier": {"selected_option": {"value": "Tier 1"}}},
    }
    payload = _seller_edit_form_payload(
        seller_id, "org-attio-1", ["hq_country"], ["outreach_tier"], values
    )

    response = _post_interactivity(payload)

    assert response.status_code == 200
    assert postgres_calls == []
    text = _mock_slack_web_client.posted[0]["text"]
    assert "Couldn't write to Attio, nothing was saved" not in text
    assert "organization fields" in text


def test_edit_form_removed_org_is_rejected_before_any_write(
    monkeypatch, _mock_slack_web_client
) -> None:
    from datetime import UTC, datetime

    seller_id = str(uuid.uuid4())
    org = _fake_org(attio_id="org-attio-1", removed_at=datetime.now(UTC))
    monkeypatch.setattr(
        actions_module,
        "resolve_seller_by_id",
        _async_returning(_fake_seller_role(seller_id, org=org)),
    )

    attio_calls: list = []

    async def fake_build_attio_values(*_args, **_kwargs):
        attio_calls.append("called")
        return {}

    monkeypatch.setattr(actions_module, "build_attio_values", fake_build_attio_values)
    monkeypatch.setattr(actions_module, "get_attio_client", lambda: object())

    values = {"outreach_tier": {"outreach_tier": {"selected_option": {"value": "Tier 1"}}}}
    payload = _seller_edit_form_payload(seller_id, "org-attio-1", [], ["outreach_tier"], values)

    response = _post_interactivity(payload)

    assert response.status_code == 200
    assert attio_calls == []
    assert "gone or was merged" in _mock_slack_web_client.posted[0]["text"]


def test_gated_field_without_confirmation_requires_checkbox() -> None:
    seller_id = str(uuid.uuid4())
    values = {"intake_source": {"intake_source": {"selected_option": {"value": "Direct"}}}}
    payload = _seller_edit_form_payload(seller_id, "org-attio-1", [], ["intake_source"], values)

    response = _post_interactivity(payload)

    assert response.status_code == 200
    body = response.json()
    assert body["response_action"] == "errors"
    assert "gated_field_confirmation" in body["errors"]


# --------------------------------------------------------------------------
# buyer symmetry smoke test
# --------------------------------------------------------------------------


def test_buyer_edit_form_writes_attio_before_postgres(monkeypatch, _mock_slack_web_client) -> None:
    buyer_id = str(uuid.uuid4())
    org = _fake_org(attio_id="org-attio-2", name="Blue Horizon")
    monkeypatch.setattr(
        actions_module, "resolve_buyer_by_id", _async_returning(_fake_buyer_role(buyer_id, org=org))
    )

    async def fake_build_attio_values(*_args, **_kwargs):
        return {"model": "opt-model-1"}

    async def fake_resolve_role_entry_id(*_args, **_kwargs):
        return "entry-2"

    async def fake_patch_role_entry(*_args, **_kwargs):
        return None

    postgres_use_case = SimpleNamespace(calls=[])

    async def fake_execute(*args, **kwargs):
        postgres_use_case.calls.append((args, kwargs))
        return None

    monkeypatch.setattr(actions_module, "build_attio_values", fake_build_attio_values)
    monkeypatch.setattr(actions_module, "resolve_role_entry_id", fake_resolve_role_entry_id)
    monkeypatch.setattr(actions_module, "patch_role_entry", fake_patch_role_entry)
    monkeypatch.setattr(actions_module, "get_attio_client", lambda: object())
    monkeypatch.setattr(
        actions_module,
        "build_update_buyer_use_case",
        lambda: SimpleNamespace(execute=fake_execute),
    )

    payload = {
        "type": "view_submission",
        "user": {"id": "U_TEST"},
        "view": {
            "type": "modal",
            "id": "V4",
            "callback_id": "buyer_edit_form_modal",
            "private_metadata": json.dumps(
                {
                    "buyer_role_id": buyer_id,
                    "org_attio_id": "org-attio-2",
                    "org_name": "Blue Horizon",
                    "requested_by": "U_TEST",
                    "channel_id": "C_TEST",
                    "selected_org_fields": [],
                    "selected_role_fields": ["model"],
                }
            ),
            "state": {
                "values": {
                    "model": {
                        "model": {"selected_option": {"value": "Model 1 (Network)"}}
                    }
                }
            },
        },
    }

    response = _post_interactivity(payload)

    assert response.status_code == 200
    assert len(postgres_use_case.calls) == 1
    assert "Updated buyer profile for Blue Horizon" in _mock_slack_web_client.posted[0]["text"]


# --------------------------------------------------------------------------
# /add-seller, /add-buyer: organization_selection_modal -> add-form
# --------------------------------------------------------------------------


def _organization_selection_payload(
    kind: str, search_term: str, selected_value: str, candidate_names: list[str] | None = None
) -> dict:
    return {
        "type": "view_submission",
        "user": {"id": "U_TEST"},
        "view": {
            "type": "modal",
            "id": "V5",
            "callback_id": "organization_selection_modal",
            "private_metadata": json.dumps(
                {
                    "kind": kind,
                    "search_term": search_term,
                    "requested_by": "U_TEST",
                    "channel_id": "C_TEST",
                    "candidate_names": candidate_names or [],
                }
            ),
            "state": {
                "values": {
                    "organization_id": {
                        "selected_organization": {"selected_option": {"value": selected_value}}
                    }
                }
            },
        },
    }


def test_organization_selection_new_option_opens_add_form() -> None:
    payload = _organization_selection_payload("seller", "Acme", NEW_ORGANIZATION_VALUE)

    response = _post_interactivity(payload)

    assert response.status_code == 200
    body = response.json()
    assert body["response_action"] == "update"
    assert body["view"]["callback_id"] == "seller_add_form_modal"
    metadata = json.loads(body["view"]["private_metadata"])
    assert metadata["is_new_org"] is True
    assert metadata["org_attio_id"] is None
    name_block = next(b for b in body["view"]["blocks"] if b["block_id"] == "name")
    assert name_block["element"]["initial_value"] == "Acme"


def test_organization_selection_new_option_with_candidates_shows_duplicate_warning() -> None:
    payload = _organization_selection_payload(
        "seller", "Acme", NEW_ORGANIZATION_VALUE, candidate_names=["Acme Corp", "Acme Corporation"]
    )

    response = _post_interactivity(payload)

    assert response.status_code == 200
    blocks = response.json()["view"]["blocks"]
    warning_text = blocks[0]["text"]["text"]
    assert "Acme Corp" in warning_text
    assert "Acme Corporation" in warning_text
    assert "separate organization" in warning_text


def test_organization_selection_existing_org_opens_add_form(monkeypatch) -> None:
    org = _fake_org(attio_id="org-attio-9", name="Found Co")
    monkeypatch.setattr(actions_module, "resolve_organization", _async_returning(org))

    payload = _organization_selection_payload("buyer", "Found", "org-attio-9")

    response = _post_interactivity(payload)

    assert response.status_code == 200
    body = response.json()
    assert body["response_action"] == "update"
    assert body["view"]["callback_id"] == "buyer_add_form_modal"
    metadata = json.loads(body["view"]["private_metadata"])
    assert metadata["is_new_org"] is False
    assert metadata["org_attio_id"] == "org-attio-9"
    assert metadata["org_name"] == "Found Co"


def test_organization_selection_existing_org_with_role_is_rejected(
    monkeypatch, _mock_slack_web_client
) -> None:
    org = _fake_org(attio_id="org-attio-9", name="Found Co", seller_role=SimpleNamespace())
    monkeypatch.setattr(actions_module, "resolve_organization", _async_returning(org))

    payload = _organization_selection_payload("seller", "Found", "org-attio-9")

    response = _post_interactivity(payload)

    assert response.status_code == 200
    assert response.text == ""
    assert "already has a seller role" in _mock_slack_web_client.posted[0]["text"]


def test_organization_selection_missing_org_shows_ephemeral(
    monkeypatch, _mock_slack_web_client
) -> None:
    monkeypatch.setattr(actions_module, "resolve_organization", _async_returning(None))

    payload = _organization_selection_payload("seller", "Ghost", "org-attio-ghost")

    response = _post_interactivity(payload)

    assert response.status_code == 200
    assert "could not be found" in _mock_slack_web_client.posted[0]["text"]


# --------------------------------------------------------------------------
# /add-seller, /add-buyer: add-form submission -> Attio, then Postgres
# --------------------------------------------------------------------------


def _seller_add_form_payload(
    is_new_org: bool, org_attio_id: str | None, org_name: str | None, values: dict
) -> dict:
    return {
        "type": "view_submission",
        "user": {"id": "U_TEST"},
        "view": {
            "type": "modal",
            "id": "V6",
            "callback_id": "seller_add_form_modal",
            "private_metadata": json.dumps(
                {
                    "is_new_org": is_new_org,
                    "org_attio_id": org_attio_id,
                    "org_name": org_name,
                    "requested_by": "U_TEST",
                    "channel_id": "C_TEST",
                }
            ),
            "state": {"values": values},
        },
    }


def test_seller_add_form_new_org_writes_attio_before_postgres(
    monkeypatch, _mock_slack_web_client
) -> None:
    call_order: list[str] = []

    async def fake_build_attio_values(*_args, **_kwargs):
        return {}

    async def fake_create_organization(*_args, **_kwargs):
        call_order.append("create_organization")
        return "org-new-1"

    async def fake_create_role_entry(*_args, **_kwargs):
        call_order.append("create_role_entry")
        return "entry-new-1"

    postgres_use_case = SimpleNamespace(calls=[])

    async def fake_execute(**kwargs):
        call_order.append("postgres_write")
        postgres_use_case.calls.append(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(actions_module, "build_attio_values", fake_build_attio_values)
    monkeypatch.setattr(actions_module, "create_organization", fake_create_organization)
    monkeypatch.setattr(actions_module, "create_role_entry", fake_create_role_entry)
    monkeypatch.setattr(actions_module, "get_attio_client", lambda: object())
    monkeypatch.setattr(
        actions_module,
        "build_create_seller_use_case",
        lambda: SimpleNamespace(execute=fake_execute),
    )

    values = {"name": {"name": {"value": "New Seller Co"}}}
    payload = _seller_add_form_payload(True, None, None, values)

    response = _post_interactivity(payload)

    assert response.status_code == 200
    assert response.text == ""
    assert call_order == ["create_organization", "create_role_entry", "postgres_write"]
    assert postgres_use_case.calls[0]["org_attio_id"] == "org-new-1"
    assert postgres_use_case.calls[0]["is_new_org"] is True
    assert postgres_use_case.calls[0]["org_name"] == "New Seller Co"
    assert "Added seller profile for New Seller Co" in _mock_slack_web_client.posted[0]["text"]


def test_seller_add_form_new_org_without_name_shows_error() -> None:
    payload = _seller_add_form_payload(True, None, None, {})

    response = _post_interactivity(payload)

    assert response.status_code == 200
    body = response.json()
    assert body["response_action"] == "errors"
    assert "name" in body["errors"]


def test_seller_add_form_attio_failure_prevents_postgres_write(
    monkeypatch, _mock_slack_web_client
) -> None:
    async def fake_build_attio_values(*_args, **_kwargs):
        return {}

    async def failing_create_organization(*_args, **_kwargs):
        raise AttioError(400, "bad request")

    postgres_calls: list = []

    async def fake_execute(**kwargs):
        postgres_calls.append(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(actions_module, "build_attio_values", fake_build_attio_values)
    monkeypatch.setattr(actions_module, "create_organization", failing_create_organization)
    monkeypatch.setattr(actions_module, "get_attio_client", lambda: object())
    monkeypatch.setattr(
        actions_module,
        "build_create_seller_use_case",
        lambda: SimpleNamespace(execute=fake_execute),
    )

    values = {"name": {"name": {"value": "New Seller Co"}}}
    payload = _seller_add_form_payload(True, None, None, values)

    response = _post_interactivity(payload)

    assert response.status_code == 200
    assert postgres_calls == []
    assert "Couldn't write to Attio, nothing was saved" in _mock_slack_web_client.posted[0]["text"]


def test_seller_add_form_role_entry_failure_after_org_create_reports_what_landed(
    monkeypatch, _mock_slack_web_client
) -> None:
    """Org create succeeds in Attio, then the role-entry create fails — the
    org is not rolled back (see `ddl-commands/README.md`, "the add flow"),
    and the user must be told the org now exists in Attio rather than being
    told "nothing was saved", which would be false.
    """

    async def fake_build_attio_values(*_args, **_kwargs):
        return {}

    async def fake_create_organization(*_args, **_kwargs):
        return "org-new-1"

    async def failing_create_role_entry(*_args, **_kwargs):
        raise AttioError(400, "bad request")

    postgres_calls: list = []

    async def fake_execute(**kwargs):
        postgres_calls.append(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(actions_module, "build_attio_values", fake_build_attio_values)
    monkeypatch.setattr(actions_module, "create_organization", fake_create_organization)
    monkeypatch.setattr(actions_module, "create_role_entry", failing_create_role_entry)
    monkeypatch.setattr(actions_module, "get_attio_client", lambda: object())
    monkeypatch.setattr(
        actions_module,
        "build_create_seller_use_case",
        lambda: SimpleNamespace(execute=fake_execute),
    )

    values = {"name": {"name": {"value": "New Seller Co"}}}
    payload = _seller_add_form_payload(True, None, None, values)

    response = _post_interactivity(payload)

    assert response.status_code == 200
    assert postgres_calls == []
    text = _mock_slack_web_client.posted[0]["text"]
    assert "Couldn't write to Attio, nothing was saved" not in text
    assert "New Seller Co" in text
    assert "org-new-1" in text


def test_seller_add_form_postgres_failure_after_attio_success_reports_what_landed(
    monkeypatch, _mock_slack_web_client
) -> None:
    """Both Attio writes succeed; the Postgres write then fails with a plain
    (non-`SellerAlreadyExistsError`) exception — previously this propagated
    uncaught out of the view handler with no message reaching the user at
    all. Must now surface a message naming exactly what already landed in
    Attio.
    """

    async def fake_build_attio_values(*_args, **_kwargs):
        return {}

    async def fake_create_organization(*_args, **_kwargs):
        return "org-new-1"

    async def fake_create_role_entry(*_args, **_kwargs):
        return "entry-new-1"

    async def failing_execute(**_kwargs):
        raise RuntimeError("connection reset")

    monkeypatch.setattr(actions_module, "build_attio_values", fake_build_attio_values)
    monkeypatch.setattr(actions_module, "create_organization", fake_create_organization)
    monkeypatch.setattr(actions_module, "create_role_entry", fake_create_role_entry)
    monkeypatch.setattr(actions_module, "get_attio_client", lambda: object())
    monkeypatch.setattr(
        actions_module,
        "build_create_seller_use_case",
        lambda: SimpleNamespace(execute=failing_execute),
    )

    values = {"name": {"name": {"value": "New Seller Co"}}}
    payload = _seller_add_form_payload(True, None, None, values)

    response = _post_interactivity(payload)

    assert response.status_code == 200
    text = _mock_slack_web_client.posted[0]["text"]
    assert "Couldn't write to Attio, nothing was saved" not in text
    assert "org-new-1" in text
    assert "seller role entry" in text
    assert "connection reset" in text


def test_buyer_add_form_existing_org_writes_attio_before_postgres(
    monkeypatch, _mock_slack_web_client
) -> None:
    call_order: list[str] = []

    async def fake_build_attio_values(*_args, **kwargs):
        # Org fields are all unset in this test's payload — distinguish by
        # table so the org branch doesn't accidentally return a truthy
        # value and trigger an unmocked `patch_organization` call.
        if kwargs.get("table") == "organizations":
            return {}
        return {"model": "opt-model-1"}

    async def fake_create_role_entry(*_args, **_kwargs):
        call_order.append("create_role_entry")
        return "entry-new-2"

    postgres_use_case = SimpleNamespace(calls=[])

    async def fake_execute(**kwargs):
        call_order.append("postgres_write")
        postgres_use_case.calls.append(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(actions_module, "build_attio_values", fake_build_attio_values)
    monkeypatch.setattr(actions_module, "create_role_entry", fake_create_role_entry)
    monkeypatch.setattr(actions_module, "get_attio_client", lambda: object())
    monkeypatch.setattr(
        actions_module,
        "build_create_buyer_use_case",
        lambda: SimpleNamespace(execute=fake_execute),
    )

    values = {"model": {"model": {"selected_option": {"value": "Model 1 (Network)"}}}}
    payload = {
        "type": "view_submission",
        "user": {"id": "U_TEST"},
        "view": {
            "type": "modal",
            "id": "V7",
            "callback_id": "buyer_add_form_modal",
            "private_metadata": json.dumps(
                {
                    "is_new_org": False,
                    "org_attio_id": "org-attio-existing",
                    "org_name": "Existing Buyer Co",
                    "requested_by": "U_TEST",
                    "channel_id": "C_TEST",
                }
            ),
            "state": {"values": values},
        },
    }

    response = _post_interactivity(payload)

    assert response.status_code == 200
    assert call_order == ["create_role_entry", "postgres_write"]
    assert postgres_use_case.calls[0]["org_attio_id"] == "org-attio-existing"
    assert postgres_use_case.calls[0]["is_new_org"] is False
    assert "Added buyer profile for Existing Buyer Co" in _mock_slack_web_client.posted[0]["text"]
