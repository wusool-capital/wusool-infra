"""Where every finished tool call is recorded."""

from typing import Protocol

from app.modules.mcp.domain.calls import ToolCall


class ToolCallAudit(Protocol):
    async def record(self, call: ToolCall) -> None:
        """Record `call`. Must never raise: a failed audit cannot fail the tool."""
        ...
