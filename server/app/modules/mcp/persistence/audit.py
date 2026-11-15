"""Records every tool call as one `activities` row: who called which tool, and
how it ended. The call is the row's subject; nothing from its arguments or
results is kept."""

import logging

from app.modules.activities import (
    ActivityActor,
    ActivityEvent,
    ActivitySource,
    EventType,
    McpToolCallPayload,
    SqlAlchemyActivityRecorder,
    SubjectType,
)
from app.modules.mcp.domain.calls import SUCCESS_RESULTS, ToolCall
from app.modules.mcp.persistence.database import get_sessionmaker

logger = logging.getLogger(__name__)


class ActivityToolCallAudit:
    async def record(self, call: ToolCall) -> None:
        event = ActivityEvent(
            subject_type=SubjectType.MCP_CALL,
            event_type=EventType.MCP_TOOL_CALLED,
            source=ActivitySource.MCP,
            actor=ActivityActor.slack(call.caller.slack_user_id),
            payload=McpToolCallPayload(
                tool=call.tool, result=call.result, duration_ms=call.duration_ms
            ),
            subject_uuid=call.call_id,
            outcome="succeeded" if call.result in SUCCESS_RESULTS else "failed",
        )
        try:
            async with get_sessionmaker()() as session, session.begin():
                await SqlAlchemyActivityRecorder(session).record(event)
        except Exception:
            # Opening the session can fail before the recorder's own guard applies.
            logger.exception("mcp_tool_call_audit_failed tool=%s", call.tool)
