"""Every tool call, whatever its outcome, is handed to the audit: who called
which tool and how it ended."""

import uuid
from unittest.mock import AsyncMock

import pytest
from mcp import Client

from app.modules.activities import (
    ActivityEvent,
    ActivitySource,
    ActorType,
    EventType,
    McpToolCallPayload,
    SubjectType,
)
from app.modules.ddl_commands import RecordRef
from app.modules.mcp.api.tools import records
from app.modules.mcp.bootstrap import build_server
from app.modules.mcp.domain.access import Caller
from app.modules.mcp.persistence import audit as audit_module
from app.modules.mcp.persistence.adapters import InMemoryToolCallAudit
from app.modules.mcp.persistence.audit import ActivityToolCallAudit

_CALLER = Caller(slack_user_id="U_RAMZY", team_id="T1", name="Ramzy", scopes=("crm",))
_REF = RecordRef(
    role_id=uuid.uuid4(),
    org_attio_id="org-1",
    org_name="Acme",
    domains=("acme.com",),
    target_vertical="Fintech",
)


def _server(audit: InMemoryToolCallAudit, calls_per_hour: int = 100):
    return build_server(
        public_url="https://tools.example",
        token_secret="secret",
        calls_per_hour=calls_per_hour,
        caller_source=lambda: _CALLER,
        audit=audit,
    )


async def test_a_read_call_is_audited_with_who_and_which_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(records, "find_records", AsyncMock(return_value=[_REF]))
    audit = InMemoryToolCallAudit()
    async with Client(_server(audit)) as client:
        await client.call_tool("find_buyers", {"query": "acme.com"})

    (call,) = audit.calls
    assert (call.tool, call.result) == ("find_buyers", "ok")
    assert call.caller.slack_user_id == "U_RAMZY"
    assert call.duration_ms >= 0


async def test_a_write_call_is_audited_too(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(records, "edit_one", AsyncMock(return_value=["notes"]))
    audit = InMemoryToolCallAudit()
    async with Client(_server(audit)) as client:
        await client.call_tool(
            "edit_buyer",
            {"role_id": str(_REF.role_id), "fields": {"notes": "x"}, "request_id": "req-00001"},
        )
    assert [(c.tool, c.result) for c in audit.calls] == [("edit_buyer", "ok")]


async def test_a_replayed_request_is_audited_as_a_replay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(records, "edit_one", AsyncMock(return_value=["notes"]))
    audit = InMemoryToolCallAudit()
    args = {"role_id": str(_REF.role_id), "fields": {"notes": "x"}, "request_id": "req-00001"}
    async with Client(_server(audit)) as client:
        await client.call_tool("edit_buyer", args)
        await client.call_tool("edit_buyer", args)
    assert [c.result for c in audit.calls] == ["ok", "replayed"]


async def test_a_reused_request_id_is_audited_as_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(records, "edit_one", AsyncMock(return_value=["notes"]))
    audit = InMemoryToolCallAudit()
    base = {"role_id": str(_REF.role_id), "request_id": "req-00001"}
    async with Client(_server(audit)) as client:
        await client.call_tool("edit_buyer", {**base, "fields": {"notes": "x"}})
        await client.call_tool("edit_buyer", {**base, "fields": {"notes": "different"}})
    assert [c.result for c in audit.calls] == ["ok", "request_id_reused"]


async def test_a_rate_limited_call_is_audited(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(records, "find_records", AsyncMock(return_value=[]))
    audit = InMemoryToolCallAudit()
    async with Client(_server(audit, calls_per_hour=1)) as client:
        await client.call_tool("find_buyers", {"query": "acme.com"})
        await client.call_tool("find_buyers", {"query": "acme.com"})
    assert [c.result for c in audit.calls] == ["ok", "rate_limited"]


async def test_a_crash_is_audited_as_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(records, "find_records", AsyncMock(side_effect=RuntimeError("boom")))
    audit = InMemoryToolCallAudit()
    async with Client(_server(audit)) as client:
        await client.call_tool("find_buyers", {"query": "acme.com"})
    assert [(c.tool, c.result) for c in audit.calls] == [("find_buyers", "error")]


async def test_each_call_gets_its_own_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(records, "find_records", AsyncMock(return_value=[]))
    audit = InMemoryToolCallAudit()
    async with Client(_server(audit)) as client:
        await client.call_tool("find_buyers", {"query": "acme.com"})
        await client.call_tool("find_buyers", {"query": "acme.com"})
    assert len({c.call_id for c in audit.calls}) == 2


async def test_the_adapter_builds_one_activity_naming_the_caller_and_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: list[ActivityEvent] = []

    class _Recorder:
        def __init__(self, _session: object) -> None: ...

        async def record(self, event: ActivityEvent) -> None:
            recorded.append(event)

    class _Session:
        async def __aenter__(self) -> "_Session":
            return self

        async def __aexit__(self, *_exc: object) -> None: ...

        def begin(self) -> "_Session":
            return self

    monkeypatch.setattr(audit_module, "SqlAlchemyActivityRecorder", _Recorder)
    monkeypatch.setattr(audit_module, "get_sessionmaker", lambda: lambda: _Session())
    audit = InMemoryToolCallAudit()
    monkeypatch.setattr(records, "find_records", AsyncMock(return_value=[]))
    async with Client(_server(audit)) as client:
        await client.call_tool("find_buyers", {"query": "acme.com"})
    await ActivityToolCallAudit().record(audit.calls[0])

    (event,) = recorded
    assert event.subject_type is SubjectType.MCP_CALL
    assert event.event_type is EventType.MCP_TOOL_CALLED
    assert event.source is ActivitySource.MCP
    assert event.actor.type is ActorType.SLACK_USER
    assert event.actor.ref == "U_RAMZY"
    assert event.subject_uuid == audit.calls[0].call_id
    assert event.outcome == "succeeded"
    assert isinstance(event.payload, McpToolCallPayload)
    assert (event.payload.tool, event.payload.result) == ("find_buyers", "ok")


async def test_a_failing_audit_never_fails_the_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    def _broken() -> None:
        raise ConnectionError("database down")

    monkeypatch.setattr(audit_module, "get_sessionmaker", _broken)
    monkeypatch.setattr(records, "find_records", AsyncMock(return_value=[_REF]))
    async with Client(
        build_server(
            public_url="https://tools.example",
            token_secret="secret",
            calls_per_hour=100,
            caller_source=lambda: _CALLER,
            audit=ActivityToolCallAudit(),
        )
    ) as client:
        result = await client.call_tool("find_buyers", {"query": "acme.com"})
    assert not result.is_error
