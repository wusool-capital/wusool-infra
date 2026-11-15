"""The real adapter writes a real `activities` row for a tool call."""

import uuid
from types import TracebackType

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.modules.mcp.domain.access import Caller
from app.modules.mcp.domain.calls import ToolCall
from app.modules.mcp.persistence import audit as audit_module
from app.modules.mcp.persistence.audit import ActivityToolCallAudit


class _TestSession:
    """Hands out the test's rolled-back session instead of opening a new one."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> "_TestSession":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    def begin(self) -> "_TestSession":
        return self

    async def execute(self, *args, **kwargs):
        return await self._session.execute(*args, **kwargs)

    def begin_nested(self):
        return self._session.begin_nested()


def _call(result: str) -> ToolCall:
    return ToolCall(
        call_id=uuid.uuid4(),
        tool="list_buyers",
        caller=Caller(slack_user_id="U_JULES", team_id="T1", name="Jules", scopes=("crm",)),
        result=result,
        duration_ms=42,
    )


@pytest.mark.parametrize(("result", "outcome"), [("ok", "succeeded"), ("refused", "failed")])
async def test_a_call_becomes_one_activity(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, result: str, outcome: str
) -> None:
    monkeypatch.setattr(audit_module, "get_sessionmaker", lambda: lambda: _TestSession(db_session))
    call = _call(result)
    await ActivityToolCallAudit().record(call)

    rows = list(
        await db_session.scalars(select(Activity).where(Activity.subject_uuid == call.call_id))
    )
    assert len(rows) == 1
    row = rows[0]
    assert (row.event_type, row.subject_type, row.source) == ("mcp.tool_called", "McpCall", "mcp")
    assert (row.actor_type, row.actor_ref, row.outcome) == ("slack_user", "U_JULES", outcome)
    assert row.payload == {
        "kind": "mcp_tool_call",
        "tool": "list_buyers",
        "result": result,
        "duration_ms": 42,
    }
