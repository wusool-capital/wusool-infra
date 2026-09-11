"""The ledger seam. Exists because the module's own architecture test
forbids `application/` importing `persistence/`, so the use case is typed
against this instead of `ToolRunsRepository` directly."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.modules.lead_magnets.domain.shared.tool_run import (
    Stage,
    SubjectRefs,
    Tool,
    ToolRunRecord,
    ToolRunStatus,
)
from app.modules.utilities.domain.json_types import JsonObject


class ToolRunsPort(Protocol):
    async def start(
        self, *, tool: Tool, payload: JsonObject, idempotency_key: str
    ) -> tuple[UUID, bool]: ...

    async def set_stage(
        self, run_id: UUID, *, stage: Stage, output: JsonObject | None = None
    ) -> None: ...

    async def finish(
        self,
        run_id: UUID,
        status: ToolRunStatus,
        *,
        subjects: SubjectRefs = ...,
        error: str | None = None,
    ) -> None: ...

    async def get(self, run_id: UUID) -> ToolRunRecord | None: ...

    async def claim_stale(self, *, cutoff: datetime) -> list[ToolRunRecord]: ...

    async def abandon_past_ceiling(self, *, cutoff: datetime) -> list[ToolRunRecord]: ...

    async def promote_role_fks(self) -> int: ...
