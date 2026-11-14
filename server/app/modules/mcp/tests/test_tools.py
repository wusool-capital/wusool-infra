"""Every tool through the SDK's in-memory client, with the `ddl_commands` calls faked."""

import uuid
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
    PartialWriteError,
    PreviewResult,
    RecordRef,
    RejectedUpload,
    RowProblem,
)
from app.modules.mcp.api.runner import caller_from_token
from app.modules.mcp.api.server import build_server
from app.modules.mcp.api.tools import imports, records
from app.modules.mcp.domain.access import Caller

_CALLER = Caller(slack_user_id="U_ALICE", team_id="T1", name="Alice", scopes=("crm",))
_REF = RecordRef(
    role_id=uuid.uuid4(),
    org_attio_id="org-1",
    org_name="Acme",
    domains=("acme.com",),
    target_vertical="Fintech",
)
_BUYER = {"org_name": "Acme", "domain": "acme.com", "target_vertical": "Fintech"}


def _server(calls_per_hour: int = 100) -> MCPServer:
    return build_server(
        public_url="https://tools.example",
        token_secret="secret",
        calls_per_hour=calls_per_hour,
        caller_source=lambda: _CALLER,
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
    monkeypatch.setattr(
        imports, "status", Mock(return_value=CommitProgress(state="done", total=119, added=119))
    )

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
    assert preview.await_args.kwargs == {"invoked_via": "mcp"}
    assert confirmed.structured_content is not None
    assert confirmed.structured_content["state"] == "running"
    commit.assert_called_once_with(preview_id, requested_by="U_ALICE")
    assert progress.structured_content is not None
    assert progress.structured_content["added"] == 119


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
