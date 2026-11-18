"""Every tool through the SDK's in-memory client, with the `ddl_commands` calls faked."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult, TextContent

from app.modules.ddl_commands import (
    AddOutcome,
    CommitProgress,
    InvalidFieldsError,
    InvalidFiltersError,
    PartialWriteError,
    PreviewResult,
    RecordDetail,
    RecordDetails,
    RecordList,
    RecordRef,
    RejectedUpload,
    RowProblem,
)
from app.modules.mcp.api.runner import caller_from_token
from app.modules.mcp.api.tools import imports, lookups, records
from app.modules.mcp.bootstrap import build_server
from app.modules.mcp.domain.access import Caller
from app.modules.mcp.persistence.adapters import InMemoryToolCallAudit

_CALLER = Caller(slack_user_id="U_ALICE", team_id="T1", name="Alice", scopes=("crm",))
_REF = RecordRef(
    role_id=uuid.uuid4(),
    org_attio_id="org-1",
    org_name="Acme",
    domains=("acme.com",),
    target_vertical="Fintech",
)
_BUYER = {"org_name": "Acme", "domain": "acme.com", "target_vertical": "Fintech"}


def _server(calls_per_hour: int = 100, audit: InMemoryToolCallAudit | None = None) -> MCPServer:
    return build_server(
        public_url="https://tools.example",
        token_secret="secret",
        calls_per_hour=calls_per_hour,
        caller_source=lambda: _CALLER,
        audit=audit or InMemoryToolCallAudit(),
    )


def _text(result: CallToolResult) -> str:
    return " ".join(c.text for c in result.content if isinstance(c, TextContent))


async def test_lists_every_tool_with_its_annotations() -> None:
    async with Client(_server()) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}

    assert set(tools) == {
        "find_buyers",
        "find_sellers",
        "add_buyer",
        "add_seller",
        "edit_buyer",
        "edit_seller",
        "bulk_import_buyers",
        "bulk_import_sellers",
        "confirm_import",
        "get_import",
        "get_benchmark_overview",
        "get_peer_cut",
        "edit_benchmark_peer_cut",
        "edit_revenue_band",
        "set_metric_weights",
        "get_buyer",
        "get_seller",
        "list_buyers",
        "list_sellers",
        "check_buyer",
        "list_field_options",
    }
    find = tools["find_buyers"].annotations
    assert find is not None and find.read_only_hint is True
    edit = tools["edit_buyer"].annotations
    assert edit is not None and edit.destructive_hint is True
    assert "mandate_status" in (tools["add_buyer"].description or "")


async def test_add_buyer_saves_once_per_request_id(monkeypatch: pytest.MonkeyPatch) -> None:
    add = AsyncMock(return_value=AddOutcome(status="added", record=_REF))
    monkeypatch.setattr(records, "add_one", add)
    args = {"buyer": {**_BUYER, "fields": {"notes": "x"}}, "request_id": "req-00001"}

    async with Client(_server()) as client:
        first = await client.call_tool("add_buyer", args)
        retry = await client.call_tool("add_buyer", args)

    assert first.structured_content == retry.structured_content
    assert first.structured_content is not None
    assert first.structured_content["status"] == "added"
    add.assert_awaited_once()
    assert add.await_args is not None
    assert add.await_args.args == ("buyer", {**_BUYER, "notes": "x"})
    assert add.await_args.kwargs == {"requested_by": "U_ALICE", "invoked_via": "mcp"}


async def test_an_existing_company_comes_back_as_existing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        records, "add_one", AsyncMock(return_value=AddOutcome(status="existing", record=_REF))
    )

    async with Client(_server()) as client:
        result = await client.call_tool(
            "add_seller",
            {"seller": {"org_name": "Acme", "domain": "acme.com"}, "request_id": "req-00002"},
        )

    assert result.structured_content is not None
    assert result.structured_content["status"] == "existing"
    assert result.structured_content["record"]["org_name"] == "Acme"


async def test_bad_fields_come_back_as_a_readable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    problem = RowProblem(
        row=1, kind="unknown_field", field="colour", message="unknown field 'colour'"
    )
    monkeypatch.setattr(records, "add_one", AsyncMock(side_effect=InvalidFieldsError([problem])))

    async with Client(_server()) as client:
        result = await client.call_tool("add_buyer", {"buyer": _BUYER, "request_id": "req-00003"})

    assert result.is_error
    assert "unknown field 'colour'" in _text(result)
    assert "Traceback" not in _text(result)


async def test_a_partial_attio_write_says_what_landed(monkeypatch: pytest.MonkeyPatch) -> None:
    error = PartialWriteError(["organization 'Acme' created in Attio"], RuntimeError("boom"))
    monkeypatch.setattr(records, "add_one", AsyncMock(side_effect=error))

    async with Client(_server()) as client:
        result = await client.call_tool("add_buyer", {"buyer": _BUYER, "request_id": "req-00004"})

    assert result.is_error
    assert "Already saved: organization 'Acme' created in Attio" in _text(result)
    assert "boom" not in _text(result)


async def test_an_unexpected_crash_reveals_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(records, "find_records", AsyncMock(side_effect=RuntimeError("db password")))

    async with Client(_server()) as client:
        result = await client.call_tool("find_buyers", {"query": "acme"})

    assert result.is_error
    assert "db password" not in _text(result)


async def test_edit_sends_only_the_given_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    edit = AsyncMock(return_value=("notes",))
    monkeypatch.setattr(records, "edit_one", edit)

    async with Client(_server()) as client:
        result = await client.call_tool(
            "edit_seller",
            {"role_id": str(_REF.role_id), "fields": {"notes": "hi"}, "request_id": "req-00005"},
        )

    assert result.structured_content == {
        "role_id": str(_REF.role_id),
        "changed_fields": ["notes"],
    }
    assert edit.await_args is not None
    assert edit.await_args.args == ("seller", _REF.role_id, {"notes": "hi"})


async def test_bulk_preview_refused_lists_problems(monkeypatch: pytest.MonkeyPatch) -> None:
    problem = RowProblem(row=2, kind="required", field="domain", message="domain is required")
    monkeypatch.setattr(
        imports,
        "preview_buyers",
        AsyncMock(return_value=RejectedUpload(invalid=1, problems=(problem,))),
    )

    async with Client(_server()) as client:
        result = await client.call_tool("bulk_import_buyers", {"rows": [_BUYER, _BUYER]})

    assert result.structured_content is not None
    assert result.structured_content["accepted"] is False
    assert result.structured_content["problems"] == [
        {"row": 2, "field": "domain", "message": "domain is required"}
    ]


async def test_bulk_preview_then_confirm_then_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    preview_id = uuid.uuid4()
    preview = AsyncMock(
        return_value=PreviewResult(
            preview_id=preview_id, new=119, existing=18, existing_rows=tuple(range(1, 19))
        )
    )
    monkeypatch.setattr(imports, "preview_sellers", preview)
    commit = Mock(return_value=CommitProgress(state="running", total=119))
    monkeypatch.setattr(imports, "commit", commit)
    status = Mock(return_value=CommitProgress(state="done", total=119, added=119))
    monkeypatch.setattr(imports, "status", status)

    async with Client(_server()) as client:
        previewed = await client.call_tool(
            "bulk_import_sellers", {"rows": [{"org_name": "A", "domain": "a.com"}]}
        )
        confirmed = await client.call_tool(
            "confirm_import", {"preview_id": str(preview_id), "request_id": "req-00006"}
        )
        progress = await client.call_tool("get_import", {"preview_id": str(preview_id)})

    assert previewed.structured_content is not None
    assert (previewed.structured_content["new"], previewed.structured_content["existing"]) == (
        119,
        18,
    )
    assert preview.await_args is not None
    assert preview.await_args.kwargs == {"invoked_via": "mcp", "owner": "U_ALICE"}
    assert confirmed.structured_content is not None
    assert confirmed.structured_content["state"] == "running"
    commit.assert_called_once_with(preview_id, requested_by="U_ALICE")
    assert progress.structured_content is not None
    assert progress.structured_content["added"] == 119
    status.assert_called_once_with(preview_id, requested_by="U_ALICE")


async def test_a_caller_over_the_limit_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(records, "find_records", AsyncMock(return_value=[]))

    async with Client(_server(calls_per_hour=1)) as client:
        allowed = await client.call_tool("find_sellers", {"query": "acme"})
        refused = await client.call_tool("find_sellers", {"query": "acme"})

    assert not allowed.is_error
    assert refused.is_error
    assert "Too many" in _text(refused)


def test_without_a_token_the_caller_is_refused() -> None:
    with pytest.raises(ToolError, match="Sign in"):
        caller_from_token()


async def test_a_reused_request_id_for_a_different_change_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    add = AsyncMock(return_value=AddOutcome(status="added", record=_REF))
    monkeypatch.setattr(records, "add_one", add)
    other = {**_BUYER, "org_name": "Other", "domain": "other.com"}

    async with Client(_server()) as client:
        await client.call_tool("add_buyer", {"buyer": _BUYER, "request_id": "req-00007"})
        reused = await client.call_tool("add_buyer", {"buyer": other, "request_id": "req-00007"})

    assert reused.is_error
    assert "already used for a different change" in _text(reused)
    add.assert_awaited_once()


async def test_get_buyer_returns_every_field_of_each_id_and_names_missing_ones(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing = uuid.uuid4()
    detail = RecordDetail(**_REF.model_dump(), fields={"notes": "hi", "check_size_min": 5e6})
    get = AsyncMock(return_value=RecordDetails(records=(detail,), not_found=(missing,)))
    monkeypatch.setattr(lookups, "get_records", get)

    async with Client(_server()) as client:
        result = await client.call_tool(
            "get_buyer", {"role_ids": [str(_REF.role_id), str(missing)]}
        )

    assert result.structured_content is not None
    (record,) = result.structured_content["records"]
    assert record["fields"] == {"notes": "hi", "check_size_min": 5e6}
    assert result.structured_content["not_found"] == [str(missing)]
    get.assert_awaited_once_with("buyer", [_REF.role_id, missing], None, return_all=False)


async def test_get_seller_reads_sellers(monkeypatch: pytest.MonkeyPatch) -> None:
    get = AsyncMock(return_value=RecordDetails(records=(), not_found=(_REF.role_id,)))
    monkeypatch.setattr(lookups, "get_records", get)

    async with Client(_server()) as client:
        result = await client.call_tool("get_seller", {"role_ids": [str(_REF.role_id)]})

    assert result.structured_content is not None
    assert result.structured_content["not_found"] == [str(_REF.role_id)]
    get.assert_awaited_once_with("seller", [_REF.role_id], None, return_all=False)


@pytest.mark.parametrize("count", [0, 101])
async def test_get_buyer_refuses_no_ids_or_too_many(
    monkeypatch: pytest.MonkeyPatch, count: int
) -> None:
    get = AsyncMock()
    monkeypatch.setattr(lookups, "get_records", get)

    async with Client(_server()) as client:
        result = await client.call_tool(
            "get_buyer", {"role_ids": [str(uuid.uuid4()) for _ in range(count)]}
        )

    assert result.is_error
    get.assert_not_awaited()


async def test_list_buyers_with_no_filter_lists_all_and_flags_truncation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    listed = AsyncMock(return_value=RecordList(records=(_REF,), truncated=True, next_offset=50))
    monkeypatch.setattr(lookups, "list_buyer_records", listed)

    async with Client(_server()) as client:
        result = await client.call_tool("list_buyers", {})

    assert result.structured_content is not None
    assert result.structured_content["truncated"] is True
    assert result.structured_content["next_offset"] == 50
    assert listed.await_args is not None
    assert listed.await_args.kwargs == {"filters": (), "limit": 50, "offset": 0}


async def test_the_list_tools_take_only_filters_limit_and_offset() -> None:
    async with Client(_server()) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}

    for name in ("list_buyers", "list_sellers"):
        assert set(tools[name].input_schema["properties"]) == {"filters", "limit", "offset"}


async def test_list_buyers_takes_typed_filters_on_any_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    listed = AsyncMock(return_value=RecordList(records=(), truncated=False))
    monkeypatch.setattr(lookups, "list_buyer_records", listed)

    async with Client(_server()) as client:
        await client.call_tool(
            "list_buyers",
            {
                "filters": [
                    {"field": "region", "op": "in", "value": ["GCC"]},
                    {"field": "ebitda_ceiling", "op": "gte", "value": 2e6},
                    {"field": "notes", "op": "is_set"},
                ]
            },
        )

    assert listed.await_args is not None
    sent = listed.await_args.kwargs["filters"]
    assert [(f.field, f.op) for f in sent] == [
        ("region", "in"),
        ("ebitda_ceiling", "gte"),
        ("notes", "is_set"),
    ]


@pytest.mark.parametrize(
    "bad",
    [
        {"field": "region", "op": "like", "value": "GCC"},
        {"field": "region", "op": "in", "value": []},
        {"field": "region", "op": "in", "value": "GCC"},
        {"field": "notes", "op": "is_set", "value": 1},
        {"op": "is_set"},
    ],
)
async def test_a_malformed_filter_is_refused_before_any_query(
    monkeypatch: pytest.MonkeyPatch, bad: dict[str, str | float | bool | list[str]]
) -> None:
    listed = AsyncMock()
    monkeypatch.setattr(lookups, "list_seller_records", listed)

    async with Client(_server()) as client:
        result = await client.call_tool("list_sellers", {"filters": [bad]})

    assert result.is_error
    listed.assert_not_awaited()


async def test_more_than_ten_filters_are_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    listed = AsyncMock()
    monkeypatch.setattr(lookups, "list_buyer_records", listed)
    many = [{"field": "notes", "op": "is_set"}] * 11

    async with Client(_server()) as client:
        result = await client.call_tool("list_buyers", {"filters": many})

    assert result.is_error
    listed.assert_not_awaited()


async def test_list_sellers_takes_an_offset_and_a_limit_up_to_50(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    listed = AsyncMock(return_value=RecordList(records=(), truncated=False))
    monkeypatch.setattr(lookups, "list_seller_records", listed)

    async with Client(_server()) as client:
        result = await client.call_tool("list_sellers", {"limit": 50, "offset": 100})

    assert result.structured_content is not None
    assert result.structured_content["next_offset"] is None
    assert listed.await_args is not None
    assert listed.await_args.kwargs["limit"] == 50
    assert listed.await_args.kwargs["offset"] == 100


async def test_a_bad_filter_value_sends_the_agent_to_list_field_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem = RowProblem(
        row=1,
        kind="not_allowed",
        field="outreach_tier",
        message="'gold' is not allowed for outreach_tier. Call list_field_options for values",
    )
    monkeypatch.setattr(
        lookups, "list_seller_records", AsyncMock(side_effect=InvalidFiltersError([problem]))
    )

    async with Client(_server()) as client:
        result = await client.call_tool(
            "list_sellers",
            {"filters": [{"field": "outreach_tier", "op": "eq", "value": "gold"}]},
        )

    assert result.is_error
    assert "Fix these filters" in _text(result)
    assert "Call list_field_options for values" in _text(result)
    assert "saved" not in _text(result) and "row 1" not in _text(result)


async def test_check_buyer_reports_gaps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lookups, "get_record", AsyncMock())
    report = SimpleNamespace(
        is_clear=False,
        conflicts=(),
        missing=(SimpleNamespace(criterion="ticket_band", stored="not set", stated=None),),
    )
    check = AsyncMock(return_value=SimpleNamespace(report=report, message="1 gap"))
    monkeypatch.setattr(lookups, "check_buyer_by_id", check)

    async with Client(_server()) as client:
        result = await client.call_tool("check_buyer", {"role_id": str(_REF.role_id)})

    assert result.structured_content is not None
    assert result.structured_content["clear"] is False
    assert result.structured_content["missing"] == [
        {"criterion": "ticket_band", "stored": "not set", "stated": None}
    ]
    check.assert_awaited_once_with(str(_REF.role_id), None)


async def test_check_buyer_refuses_an_unknown_buyer(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.modules.ddl_commands import BuyerNotFoundError

    monkeypatch.setattr(lookups, "get_record", AsyncMock(side_effect=BuyerNotFoundError("x")))
    check = AsyncMock()
    monkeypatch.setattr(lookups, "check_buyer_by_id", check)

    async with Client(_server()) as client:
        result = await client.call_tool("check_buyer", {"role_id": str(_REF.role_id)})

    assert result.is_error
    assert "find_buyers" in _text(result)
    check.assert_not_awaited()


async def test_list_field_options_has_every_column_and_long_lists_leave_descriptions() -> None:
    async with Client(_server()) as client:
        result = await client.call_tool("list_field_options", {"kind": "buyer"})
        tools = {t.name: t for t in (await client.list_tools()).tools}

    assert result.structured_content is not None
    by_key = {f["key"]: f for f in result.structured_content["fields"]}
    assert by_key["org_name"]["required"] is True
    assert "Fintech" in by_key["target_vertical"]["options"]
    description = tools["add_buyer"].description or ""
    assert "see list_field_options" in description
    assert "Fintech |" not in description
    assert "one of Active | Paused" in description


async def test_get_passes_the_requested_fields_through(monkeypatch: pytest.MonkeyPatch) -> None:
    get = AsyncMock(return_value=RecordDetails(records=(), not_found=()))
    monkeypatch.setattr(lookups, "get_records", get)

    async with Client(_server()) as client:
        await client.call_tool(
            "get_seller",
            {"role_ids": [str(_REF.role_id)], "fields": ["benchmark_score", "est_ebitda"]},
        )

    get.assert_awaited_once_with(
        "seller", [_REF.role_id], ["benchmark_score", "est_ebitda"], return_all=False
    )


async def test_return_all_is_passed_through_and_defaults_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get = AsyncMock(return_value=RecordDetails(records=(), not_found=()))
    monkeypatch.setattr(lookups, "get_records", get)

    async with Client(_server()) as client:
        await client.call_tool("get_buyer", {"role_ids": [str(_REF.role_id)], "return_all": True})
        tools = {t.name: t for t in (await client.list_tools()).tools}

    get.assert_awaited_once_with("buyer", [_REF.role_id], None, return_all=True)
    schema = tools["get_buyer"].input_schema["properties"]
    assert set(schema) == {"role_ids", "fields", "return_all"}
    assert schema["return_all"]["default"] is False
    for text in (schema["return_all"]["description"], tools["get_buyer"].description or ""):
        assert "only" in text and "lacks" in text  # the agent is told when not to use it


async def test_a_list_page_over_50_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    listed = AsyncMock()
    monkeypatch.setattr(lookups, "list_buyer_records", listed)

    async with Client(_server()) as client:
        result = await client.call_tool("list_buyers", {"limit": 51})

    assert result.is_error
    listed.assert_not_awaited()


async def test_return_all_for_too_many_ids_says_how_many_are_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.modules.ddl_commands import ReturnAllTooLargeError

    monkeypatch.setattr(lookups, "get_records", AsyncMock(side_effect=ReturnAllTooLargeError(30)))

    async with Client(_server()) as client:
        result = await client.call_tool(
            "get_seller", {"role_ids": [str(uuid.uuid4()) for _ in range(30)], "return_all": True}
        )

    assert result.is_error
    assert "at most 25" in _text(result) and "you sent 30" in _text(result)
    assert "`fields`" in _text(result)


async def test_an_unknown_field_key_is_named_with_the_tool_to_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.modules.ddl_commands import InvalidFieldKeysError

    problem = RowProblem(
        row=1, kind="unknown_field", field="nope", message="'nope' is not a buyer field"
    )
    monkeypatch.setattr(
        lookups, "get_records", AsyncMock(side_effect=InvalidFieldKeysError([problem]))
    )

    async with Client(_server()) as client:
        result = await client.call_tool(
            "get_buyer", {"role_ids": [str(_REF.role_id)], "fields": ["nope"]}
        )

    assert result.is_error
    assert "list_field_options" in _text(result)
    assert "'nope' is not a buyer field" in _text(result)
    assert "saved" not in _text(result)


async def test_list_field_options_includes_every_filterable_column_with_its_operators() -> None:
    async with Client(_server()) as client:
        result = await client.call_tool("list_field_options", {"kind": "seller"})

    assert result.structured_content is not None
    by_key = {f["key"]: f for f in result.structured_content["fields"]}
    assert by_key["est_ebitda"]["editable"] is True
    assert by_key["est_ebitda"]["filter_ops"] == ["gte", "lte", "eq", "is_set", "is_not_set"]
    assert by_key["benchmark_score"]["editable"] is False  # computed, but filterable
    assert "gte" in by_key["benchmark_score"]["filter_ops"]
    assert by_key["last_interaction_at"]["kind"] == "datetime"
    assert by_key["org_name"]["filter_ops"] == []  # add-only
    assert "raw_attio" not in by_key and "removed_at" not in by_key and "id" not in by_key


async def test_list_field_options_can_return_just_the_fields_asked_for() -> None:
    async with Client(_server()) as client:
        result = await client.call_tool(
            "list_field_options", {"kind": "buyer", "fields": ["target_vertical", "ebitda_ceiling"]}
        )
        unknown = await client.call_tool(
            "list_field_options", {"kind": "buyer", "fields": ["target_vertical", "nope"]}
        )

    assert result.structured_content is not None
    keys = [f["key"] for f in result.structured_content["fields"]]
    assert sorted(keys) == ["ebitda_ceiling", "target_vertical"]
    assert unknown.is_error and "'nope' is not a buyer field" in _text(unknown)


async def test_add_and_bulk_descriptions_say_which_keys_are_required() -> None:
    async with Client(_server()) as client:
        tools = {t.name: t.description or "" for t in (await client.list_tools()).tools}

    for name in ("add_buyer", "bulk_import_buyers"):
        required = tools[name].split("Everything in `fields` is optional")[0]
        assert "Required, at the top level of the record" in required
        assert all(key in required for key in ("org_name", "domain", "target_vertical"))
    for name in ("add_seller", "bulk_import_sellers"):
        required = tools[name].split("Everything in `fields` is optional")[0]
        assert "org_name" in required and "domain" in required
        assert "target_vertical" not in required


async def test_edit_descriptions_say_only_the_role_id_is_required() -> None:
    async with Client(_server()) as client:
        tools = {t.name: t.description or "" for t in (await client.list_tools()).tools}

    assert "Required: role_id only" in tools["edit_buyer"]
    assert "org_name, domain, target_vertical can't be edited" in tools["edit_buyer"]
    assert "Required: role_id only" in tools["edit_seller"]
    assert "org_name, domain can't be edited" in tools["edit_seller"]
    assert "Required, at the top level" not in tools["edit_buyer"]
    assert "Send null to empty a field" in tools["edit_buyer"]
    assert (
        "target_region, sector_focus" in tools["edit_buyer"]
        or "target_region" in tools["edit_buyer"]
    )


async def test_edit_does_not_require_fields_in_the_schema() -> None:
    async with Client(_server()) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
    for name in ("edit_buyer", "edit_seller"):
        assert tools[name].input_schema["required"] == ["role_id", "request_id"]


async def test_an_edit_with_no_fields_gets_the_server_sentence_not_a_schema_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    edit = AsyncMock(
        side_effect=InvalidFieldsError(
            [RowProblem(row=1, kind="required", message="send at least one field")]
        )
    )
    monkeypatch.setattr(records, "edit_one", edit)
    async with Client(_server()) as client:
        result = await client.call_tool(
            "edit_buyer", {"role_id": str(_REF.role_id), "request_id": "req-00009"}
        )

    assert result.is_error
    assert "send at least one field" in _text(result)
    assert edit.await_args is not None
    assert edit.await_args.args[2] == {}
