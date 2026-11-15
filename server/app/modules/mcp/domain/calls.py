"""One finished tool call, as the audit sees it."""

from dataclasses import dataclass
from uuid import UUID

from app.modules.mcp.domain.access import Caller

# Results that mean the person got what they asked for.
SUCCESS_RESULTS = frozenset({"ok", "replayed"})


@dataclass(frozen=True)
class ToolCall:
    call_id: UUID
    tool: str
    caller: Caller
    # `ok`, `replayed`, `refused`, `forbidden`, `rate_limited`, `request_id_reused`, `error`,
    # or the name of the expected error that stopped the call.
    result: str
    duration_ms: int
