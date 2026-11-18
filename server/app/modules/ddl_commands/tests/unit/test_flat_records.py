"""One add, edit or find from a flat field map, as the Wusool MCP sends it."""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import TypeAdapter

from app.modules.ddl_commands.api import flat_records
from app.modules.ddl_commands.api.bulk_store import UploadKind
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
        AsyncMock(
            return_value=SimpleNamespace(org_attio_id="org-1", is_active=True, removed_at=None)
        ),
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


async def test_edit_empties_a_field_sent_as_null_or_blank(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        flat_records,
        "resolve_buyer_by_id",
        AsyncMock(
            return_value=SimpleNamespace(org_attio_id="org-1", is_active=True, removed_at=None)
        ),
    )
    write = AsyncMock()
    monkeypatch.setattr(flat_records, "write_buyer_edit", write)

    changed = await flat_records.edit_one(
        "buyer",
        _ROLE_ID,
        {"notes": None, "ebitda_floor": None, "hq_country": "  ", "relationship_warmth": "Warm"},
        requested_by="U1",
        invoked_via="mcp",
    )

    assert changed == ("ebitda_floor", "hq_country", "notes", "relationship_warmth")
    assert write.await_args is not None
    kwargs = write.await_args.kwargs
    assert kwargs["role_extracted"] == {
        "notes": None,
        "ebitda_floor": None,
        "relationship_warmth": "Warm",
    }
    assert kwargs["org_extracted"] == {"hq_country": None}


@pytest.mark.parametrize(
    ("kind", "field"), [("buyer", "target_region"), ("seller", "sector_focus")]
)
async def test_edit_refuses_to_empty_a_list_backed_field_instead_of_ignoring_it(
    monkeypatch: pytest.MonkeyPatch, kind: str, field: str
) -> None:
    lookup = AsyncMock()
    monkeypatch.setattr(flat_records, "resolve_buyer_by_id", lookup)
    monkeypatch.setattr(flat_records, "resolve_seller_by_id", lookup)

    with pytest.raises(flat_records.InvalidFieldsError, match="can't be emptied"):
        await flat_records.edit_one(
            kind, _ROLE_ID, {field: None}, requested_by="U1", invoked_via="mcp"
        )

    lookup.assert_not_awaited()


async def test_find_by_domain_lists_only_active_roles(
    monkeypatch: pytest.MonkeyPatch, org_lookup: AsyncMock
) -> None:
    org_lookup.return_value = _org(buyers=(_buyer(), _buyer("Education", active=False)))
    monkeypatch.setattr(
        flat_records, "find_organization_by_domains", AsyncMock(return_value=_org())
    )

    found = await flat_records.find_records("buyer", "www.acme.com")

    assert [r.target_vertical for r in found] == [_VERTICAL]


def _removed(role: flat_records.BuyerRole) -> flat_records.BuyerRole:
    """Attio deleted it: `removed_at` is set and `is_active` still true."""
    role.removed_at = datetime.now(UTC)
    return role


async def test_find_leaves_out_a_role_attio_deleted(
    monkeypatch: pytest.MonkeyPatch, org_lookup: AsyncMock
) -> None:
    org_lookup.return_value = _org(buyers=(_buyer(), _removed(_buyer("Banking"))))
    monkeypatch.setattr(
        flat_records, "find_organization_by_domains", AsyncMock(return_value=_org())
    )

    found = await flat_records.find_records("buyer", "www.acme.com")

    assert [r.target_vertical for r in found] == [_VERTICAL]


@pytest.mark.parametrize("kind", ["buyer", "seller"])
async def test_edit_of_a_role_attio_deleted_raises_not_found(
    monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    role = _removed(_buyer())
    monkeypatch.setattr(flat_records, "resolve_buyer_by_id", AsyncMock(return_value=role))
    monkeypatch.setattr(flat_records, "resolve_seller_by_id", AsyncMock(return_value=role))
    write_buyer, write_seller = AsyncMock(), AsyncMock()
    monkeypatch.setattr(flat_records, "write_buyer_edit", write_buyer)
    monkeypatch.setattr(flat_records, "write_seller_edit", write_seller)
    expected = BuyerNotFoundError if kind == "buyer" else flat_records.SellerNotFoundError

    with pytest.raises(expected):
        await flat_records.edit_one(
            kind, _ROLE_ID, {"description": "hi"}, requested_by="U1", invoked_via="mcp"
        )

    write_buyer.assert_not_awaited()
    write_seller.assert_not_awaited()


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


def test_stored_values_come_back_in_the_shape_edit_accepts() -> None:
    from datetime import date
    from decimal import Decimal

    assert flat_records._plain({"amount": 5000000, "currency": "USD"}) == 5000000.0
    assert flat_records._plain({"currency": "USD"}) is None
    assert flat_records._plain(date(2026, 1, 31)) == "2026-01-31"
    assert flat_records._plain(Decimal("12.5")) == 12.5
    assert flat_records._plain(["UAE"]) == ["UAE"]
    assert flat_records._plain(True) is True
    assert flat_records._plain(None) is None
    assert flat_records._plain({"amount": "5000000", "currency": "USD"}) == 5000000.0
    assert flat_records._plain({"amount": "lots"}) is None


async def test_get_of_an_inactive_buyer_raises_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        flat_records, "resolve_buyer_by_id", AsyncMock(return_value=_buyer(active=False))
    )

    with pytest.raises(BuyerNotFoundError):
        await flat_records.get_record("buyer", _ROLE_ID)


async def test_get_records_keeps_input_order_and_names_every_missing_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first, second, inactive, unknown = (uuid.uuid4() for _ in range(4))
    live_org = SimpleNamespace(removed_at=None)
    roles = [
        SimpleNamespace(id=second, is_active=True, removed_at=None, organization=live_org),
        SimpleNamespace(id=first, is_active=True, removed_at=None, organization=live_org),
        SimpleNamespace(id=inactive, is_active=False, removed_at=None, organization=live_org),
    ]
    resolve = AsyncMock(return_value=roles)
    service = SimpleNamespace(resolve_buyers_by_ids=resolve)
    monkeypatch.setattr(flat_records, "ddl_commands_service", lambda: service)
    monkeypatch.setattr(
        flat_records,
        "_detail",
        lambda role, _selected: flat_records.RecordDetail(
            role_id=role.id, org_attio_id="org-1", org_name="Acme", domains=(), fields={}
        ),
    )

    found = await flat_records.get_records("buyer", [first, second, first, inactive, unknown])

    resolve.assert_awaited_once_with([str(first), str(second), str(inactive), str(unknown)])
    assert [d.role_id for d in found.records] == [first, second]
    assert found.not_found == (inactive, unknown)


RawFilter = dict[str, str | float | bool | list[str]]


def _filters(*items: RawFilter) -> list[flat_records.FieldFilter]:
    adapter: TypeAdapter[flat_records.FieldFilter] = TypeAdapter(flat_records.FieldFilter)
    return [adapter.validate_python(item) for item in items]


async def test_list_filters_are_checked_before_any_query(monkeypatch: pytest.MonkeyPatch) -> None:
    service = SimpleNamespace(list_buyers=AsyncMock())
    monkeypatch.setattr(flat_records, "ddl_commands_service", lambda: service)

    with pytest.raises(flat_records.InvalidFiltersError) as caught:
        await flat_records.list_buyer_records(
            filters=_filters(
                {"field": "mandate_status", "op": "eq", "value": "sleeping"},
                {"field": "target_country", "op": "in", "value": ["Mars"]},
                {"field": "no_such_field", "op": "is_set"},
            )
        )

    assert {p.field for p in caught.value.problems} == {
        "mandate_status",
        "target_country",
        "no_such_field",
    }
    service.list_buyers.assert_not_awaited()


async def test_list_hands_the_service_canonical_conditions_and_reports_truncation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roles = [
        SimpleNamespace(id=uuid.uuid4(), is_active=True, organization=_org()) for _ in range(3)
    ]
    service = SimpleNamespace(list_buyers=AsyncMock(return_value=roles))
    monkeypatch.setattr(flat_records, "ddl_commands_service", lambda: service)

    found = await flat_records.list_buyer_records(
        filters=_filters({"field": "mandate_status", "op": "eq", "value": "active"}), limit=2
    )

    wanted, limit, offset = service.list_buyers.await_args.args
    assert [(c.column, c.op, c.value) for c in wanted.conditions] == [
        ("mandate_status", "eq", "Active")
    ]
    assert limit == 3  # one extra, to know whether more match
    assert offset == 0
    assert len(found.records) == 2 and found.truncated is True
    assert found.next_offset == 2


async def test_no_filter_hands_the_service_no_conditions(monkeypatch: pytest.MonkeyPatch) -> None:
    service = SimpleNamespace(list_sellers=AsyncMock(return_value=[]))
    monkeypatch.setattr(flat_records, "ddl_commands_service", lambda: service)

    await flat_records.list_seller_records()

    wanted, limit, offset = service.list_sellers.await_args.args
    assert (wanted.conditions, limit, offset) == ((), 21, 0)


async def test_the_next_page_starts_after_the_last_returned_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roles = [
        SimpleNamespace(id=uuid.uuid4(), is_active=True, organization=_org()) for _ in range(3)
    ]
    service = SimpleNamespace(list_sellers=AsyncMock(return_value=roles))
    monkeypatch.setattr(flat_records, "ddl_commands_service", lambda: service)

    page = await flat_records.list_seller_records(limit=2, offset=4)
    last = await flat_records.list_seller_records(limit=3, offset=4)

    assert page.next_offset == 6
    assert last.truncated is False and last.next_offset is None


async def test_get_of_a_buyer_whose_company_was_removed_raises_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import UTC, datetime

    role = SimpleNamespace(
        is_active=True,
        removed_at=None,
        organization=SimpleNamespace(removed_at=datetime.now(UTC)),
    )
    monkeypatch.setattr(flat_records, "resolve_buyer_by_id", AsyncMock(return_value=role))

    with pytest.raises(BuyerNotFoundError):
        await flat_records.get_record("buyer", _ROLE_ID)


async def test_a_bad_filter_names_the_filter_the_caller_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        flat_records, "ddl_commands_service", lambda: SimpleNamespace(list_sellers=AsyncMock())
    )

    with pytest.raises(flat_records.InvalidFiltersError) as caught:
        await flat_records.list_seller_records(
            filters=_filters({"field": "sector_focus", "op": "eq", "value": "Fintechh"})
        )

    (problem,) = caught.value.problems
    assert problem.field == "sector_focus"
    assert problem.message.startswith("'Fintechh' is not allowed for sector_focus.")
    assert "list_field_options" in problem.message


def test_get_record_still_returns_every_editable_field_for_the_edit_flow() -> None:
    from app.modules.ddl_commands.api.bulk_columns import routes_for

    selected = flat_records._selected("seller", None, default="editable")

    assert [f.key for f in selected] == list(routes_for("seller"))
    assert all(f.editable for f in selected)


@pytest.mark.parametrize("kind", ["buyer", "seller"])
def test_every_advisor_field_is_in_the_catalog(kind: UploadKind) -> None:
    from app.modules.ddl_commands.api.advisor_fields import ADVISOR_FIELDS
    from app.modules.ddl_commands.api.filter_catalog import filter_catalog

    keys = ADVISOR_FIELDS[kind]

    assert len(keys) == len(set(keys))
    assert all(filter_catalog(kind).get(key) is not None for key in keys)


def test_the_advisor_template_is_the_default_and_leaves_the_junk_out() -> None:
    selected = [f.key for f in flat_records._selected("seller", None, default="advisor")]

    assert "est_ebitda" in selected and "benchmark_score" in selected
    assert "last_interaction_at" in selected
    assert not {"created_at", "pct_ebitda_margin", "twitter", "logo_url", "review_note"} & set(
        selected
    )
    every = flat_records._selected("seller", None, default="all")
    assert 0 < len(selected) < len(every)


def test_return_all_gives_every_catalog_column() -> None:
    from app.modules.ddl_commands.api.filter_catalog import filter_catalog

    selected = flat_records._selected("buyer", None, default="all")

    assert selected == filter_catalog("buyer").fields


def test_fields_win_over_the_default_and_keep_the_order_asked() -> None:
    selected = flat_records._selected(
        "seller", ["benchmark_score", "est_ebitda", "benchmark_score"], default="all"
    )

    assert [(f.key, f.editable) for f in selected] == [
        ("benchmark_score", False),
        ("est_ebitda", True),
    ]


def test_an_unknown_field_key_names_every_bad_key() -> None:
    with pytest.raises(flat_records.InvalidFieldKeysError) as caught:
        flat_records._selected("buyer", ["ebitda_ceiling", "nope", "also_nope"], default="advisor")

    assert [p.field for p in caught.value.problems] == ["nope", "also_nope"]


def _ids(count: int) -> list[uuid.UUID]:
    return [uuid.uuid4() for _ in range(count)]


async def test_return_all_refuses_more_ids_than_it_allows_before_any_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SimpleNamespace(resolve_sellers_by_ids=AsyncMock())
    monkeypatch.setattr(flat_records, "ddl_commands_service", lambda: service)

    with pytest.raises(flat_records.ReturnAllTooLargeError) as caught:
        await flat_records.get_records(
            "seller", _ids(flat_records.RETURN_ALL_IDS_MAX + 1), return_all=True
        )

    assert caught.value.count == flat_records.RETURN_ALL_IDS_MAX + 1
    service.resolve_sellers_by_ids.assert_not_awaited()


async def test_return_all_allows_exactly_the_cap_and_counts_distinct_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SimpleNamespace(resolve_sellers_by_ids=AsyncMock(return_value=[]))
    monkeypatch.setattr(flat_records, "ddl_commands_service", lambda: service)
    ids = _ids(flat_records.RETURN_ALL_IDS_MAX)

    found = await flat_records.get_records("seller", [*ids, *ids], return_all=True)

    assert found.records == () and len(found.not_found) == flat_records.RETURN_ALL_IDS_MAX


async def test_the_cap_does_not_apply_to_the_template_or_to_named_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SimpleNamespace(resolve_sellers_by_ids=AsyncMock(return_value=[]))
    monkeypatch.setattr(flat_records, "ddl_commands_service", lambda: service)
    many = _ids(flat_records.GET_IDS_MAX)

    await flat_records.get_records("seller", many)
    await flat_records.get_records("seller", many, ["est_ebitda"], return_all=True)

    assert service.resolve_sellers_by_ids.await_count == 2
