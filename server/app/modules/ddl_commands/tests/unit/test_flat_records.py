"""One add, edit or find from a flat field map, as the Wusool MCP sends it."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.modules.ddl_commands.api import flat_records
from app.modules.ddl_commands.api.bulk_upload import RowMatch
from app.modules.ddl_commands.application.buyers import BuyerNotFoundError

_ROLE_ID = uuid.uuid4()
_VERTICAL = "Fintech"


def _org(*, buyers: tuple[flat_records.BuyerRole, ...] = ()) -> SimpleNamespace:
    return SimpleNamespace(
        attio_id="org-1",
        name="Acme",
        domains=["acme.com"],
        buyer_roles=list(buyers),
        seller_roles=[],
    )


def _buyer(vertical: str = _VERTICAL, *, active: bool = True) -> flat_records.BuyerRole:
    role = flat_records.BuyerRole(id=_ROLE_ID, org_attio_id="org-1", target_vertical=vertical)
    role.is_active = active
    return role


@pytest.fixture
def org_lookup(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    lookup = AsyncMock(return_value=_org(buyers=(_buyer(),)))
    monkeypatch.setattr(flat_records, "resolve_organization", lookup)
    return lookup


async def test_an_invalid_add_writes_nothing_and_names_each_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    add = AsyncMock()
    monkeypatch.setattr(flat_records, "add_row", add)

    with pytest.raises(flat_records.InvalidFieldsError) as caught:
        await flat_records.add_one(
            "buyer", {"org_name": "Acme", "colour": "red"}, requested_by="U1", invoked_via="mcp"
        )

    assert {p.field for p in caught.value.problems} >= {"domain", "target_vertical", "colour"}
    add.assert_not_awaited()


async def test_an_existing_company_returns_the_existing_record(
    monkeypatch: pytest.MonkeyPatch, org_lookup: AsyncMock
) -> None:
    monkeypatch.setattr(flat_records, "match_row", AsyncMock(return_value=RowMatch("org-1", True)))
    add = AsyncMock()
    monkeypatch.setattr(flat_records, "add_row", add)

    outcome = await flat_records.add_one(
        "buyer",
        {"org_name": "Acme", "domain": "https://www.acme.com/", "target_vertical": _VERTICAL},
        requested_by="U1",
        invoked_via="mcp",
    )

    assert outcome.status == "existing"
    assert outcome.record.role_id == _ROLE_ID
    add.assert_not_awaited()


async def test_a_new_company_is_added_with_the_person_and_source(
    monkeypatch: pytest.MonkeyPatch, org_lookup: AsyncMock
) -> None:
    monkeypatch.setattr(flat_records, "match_row", AsyncMock(return_value=RowMatch(None, False)))
    add = AsyncMock(return_value=SimpleNamespace(org_attio_id="org-1"))
    monkeypatch.setattr(flat_records, "add_row", add)

    outcome = await flat_records.add_one(
        "buyer",
        {"org_name": "Acme", "domain": "acme.com", "target_vertical": _VERTICAL},
        requested_by="U1",
        invoked_via="mcp",
    )

    assert outcome.status == "added"
    assert outcome.record.org_name == "Acme"
    assert add.await_args is not None
    assert add.await_args.args[3:] == ("U1", "mcp")


async def test_edit_refuses_a_vertical_change_before_any_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lookup = AsyncMock()
    monkeypatch.setattr(flat_records, "resolve_buyer_by_id", lookup)

    with pytest.raises(flat_records.InvalidFieldsError):
        await flat_records.edit_one(
            "buyer",
            _ROLE_ID,
            {"target_vertical": "Education"},
            requested_by="U1",
            invoked_via="mcp",
        )

    lookup.assert_not_awaited()


async def test_edit_of_an_unknown_buyer_raises_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(flat_records, "resolve_buyer_by_id", AsyncMock(return_value=None))

    with pytest.raises(BuyerNotFoundError):
        await flat_records.edit_one(
            "buyer", _ROLE_ID, {"notes": "hi"}, requested_by="U1", invoked_via="mcp"
        )


async def test_edit_routes_org_and_role_fields_and_sends_only_those(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        flat_records,
        "resolve_buyer_by_id",
        AsyncMock(return_value=SimpleNamespace(org_attio_id="org-1", is_active=True)),
    )
    write = AsyncMock()
    monkeypatch.setattr(flat_records, "write_buyer_edit", write)

    changed = await flat_records.edit_one(
        "buyer",
        _ROLE_ID,
        {"notes": "Met in Riyadh", "hq_country": "Saudi Arabia"},
        requested_by="U1",
        invoked_via="mcp",
    )

    assert changed == ("hq_country", "notes")
    assert write.await_args is not None
    kwargs = write.await_args.kwargs
    assert kwargs["role_extracted"] == {"notes": "Met in Riyadh"}
    assert kwargs["org_extracted"] == {"hq_country": "Saudi Arabia"}
    assert (kwargs["requested_by"], kwargs["invoked_via"]) == ("U1", "mcp")


async def test_find_by_domain_lists_only_active_roles(
    monkeypatch: pytest.MonkeyPatch, org_lookup: AsyncMock
) -> None:
    org_lookup.return_value = _org(buyers=(_buyer(), _buyer("Education", active=False)))
    monkeypatch.setattr(
        flat_records, "find_organization_by_domains", AsyncMock(return_value=_org())
    )

    found = await flat_records.find_records("buyer", "www.acme.com")

    assert [r.target_vertical for r in found] == [_VERTICAL]


async def test_edit_of_an_inactive_buyer_raises_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        flat_records, "resolve_buyer_by_id", AsyncMock(return_value=_buyer(active=False))
    )
    write = AsyncMock()
    monkeypatch.setattr(flat_records, "write_buyer_edit", write)

    with pytest.raises(BuyerNotFoundError):
        await flat_records.edit_one(
            "buyer", _ROLE_ID, {"notes": "hi"}, requested_by="U1", invoked_via="mcp"
        )

    write.assert_not_awaited()


async def test_a_dotted_name_with_no_domain_match_falls_back_to_the_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(flat_records, "find_organization_by_domains", AsyncMock(return_value=None))
    role = SimpleNamespace(id=_ROLE_ID, is_active=True, organization=_org())
    resolve = AsyncMock(return_value=SimpleNamespace(candidates=[role], status="single"))
    service = SimpleNamespace(resolve_buyer=resolve)
    monkeypatch.setattr(flat_records, "ddl_commands_service", lambda: service)

    found = await flat_records.find_records("buyer", "Booking.com")

    resolve.assert_awaited_once_with("Booking.com")
    assert [r.org_name for r in found] == ["Acme"]
