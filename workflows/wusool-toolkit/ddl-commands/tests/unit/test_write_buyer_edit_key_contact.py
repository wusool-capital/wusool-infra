"""`_write_buyer_edit`'s `key_contact_attio_id` merge — the record-reference
value it builds for Attio, and the plain column it sets for Postgres, both
outside the generic `FieldSpec`/`BuyerUpdate` path (`key_contact` was never
added to either, on purpose: see `buyers/field_spec.py`).

Calls `_write_buyer_edit` directly rather than through a Slack payload,
same reasoning as `test_add_flow_reconciliation.py`: this is about what the
function does with the argument, not about wiring a view submission to it.
"""

from types import SimpleNamespace

import pytest

from ddl_commands.modules.slack.handlers import actions as actions_module

_FAKE_CLIENT = SimpleNamespace(name="fake-attio-client")


def _fake_role(org_attio_id="org-attio-1", removed_at=None):
    org = SimpleNamespace(attio_id=org_attio_id, removed_at=removed_at)
    return SimpleNamespace(organization=org)


def _async(value):
    async def _fn(*_args, **_kwargs):
        return value

    return _fn


@pytest.fixture(autouse=True)
def _stub_common(monkeypatch):
    monkeypatch.setattr(actions_module, "get_attio_client", lambda: _FAKE_CLIENT)
    monkeypatch.setattr(actions_module, "resolve_buyer_by_id", _async(_fake_role()))


async def test_key_contact_only_patches_the_record_reference_attribute(monkeypatch) -> None:
    """No other role field selected — `role_attio_values` must not be
    skipped just because `role_extracted` is empty.
    """
    patch_calls: list[tuple] = []

    async def fake_resolve_role_entry_id(*_args, **_kwargs):
        return "entry-1"

    async def fake_patch_role_entry(*args, **kwargs):
        patch_calls.append((args, kwargs))

    execute_calls: list[dict] = []

    async def fake_execute(_buyer_role_id, fields, **kwargs):
        execute_calls.append({"fields": fields, **kwargs})
        return None

    monkeypatch.setattr(actions_module, "resolve_role_entry_id", fake_resolve_role_entry_id)
    monkeypatch.setattr(actions_module, "patch_role_entry", fake_patch_role_entry)
    monkeypatch.setattr(
        actions_module, "build_update_buyer_use_case", lambda: SimpleNamespace(execute=fake_execute)
    )

    await actions_module._write_buyer_edit(
        buyer_role_id="buyer-1",
        org_attio_id="org-attio-1",
        org_extracted={},
        role_extracted={},
        key_contact_attio_id="person-attio-1",
    )

    (client, list_slug, entry_id, entry_values), _ = patch_calls[0]
    assert (client, list_slug, entry_id) == (_FAKE_CLIENT, "buyer_role", "entry-1")
    assert entry_values["key_contact"] == {
        "target_object": "person",
        "target_record_id": "person-attio-1",
    }
    assert execute_calls[0]["fields"]["key_contact_attio_id"] == "person-attio-1"


async def test_no_key_contact_and_no_role_fields_skips_the_role_patch_entirely(
    monkeypatch,
) -> None:
    """The pre-existing behavior — nothing selected means no Attio call at
    all — must survive untouched when `key_contact_attio_id` isn't given.
    """

    async def _raises_if_called(*_args, **_kwargs):
        raise AssertionError("resolve_role_entry_id should not be called")

    execute_calls: list[dict] = []

    async def fake_execute(_buyer_role_id, fields, **kwargs):
        execute_calls.append({"fields": fields, **kwargs})
        return None

    monkeypatch.setattr(actions_module, "resolve_role_entry_id", _raises_if_called)
    monkeypatch.setattr(
        actions_module, "build_update_buyer_use_case", lambda: SimpleNamespace(execute=fake_execute)
    )

    await actions_module._write_buyer_edit(
        buyer_role_id="buyer-1",
        org_attio_id="org-attio-1",
        org_extracted={},
        role_extracted={},
    )

    assert "key_contact_attio_id" not in execute_calls[0]["fields"]
