"""Every seam `application/` depends on, in one file.

Four Protocols, four network boundaries — the LLM, the web search, the Attio
write, and the ledger. The first three are what tests fake; the fourth exists
because the module's own architecture test forbids `application/` importing
`persistence/`, so the use case is typed against this instead of
`ToolRunsRepository`.

Split across four files it would be filing, not architecture.
"""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.modules.lead_magnets.domain.search import SearchResult
from app.modules.lead_magnets.domain.tool_run import (
    Stage,
    SubjectRefs,
    Tool,
    ToolRunRecord,
    ToolRunStatus,
)
from app.modules.utilities.domain.json_types import JsonObject, JsonSchema


class LeadLLMPort(Protocol):
    """Returns an already-validated plain `dict`. Pydantic models must not
    cross this seam — the same contract `meetings.SummarizerLLM` keeps.
    """

    async def invoke(
        self,
        *,
        model_id: str,
        prompt: str,
        schema: JsonSchema,
        max_tokens: int,
        temperature: float,
        system_prompt: str = "",
    ) -> JsonObject: ...


class SearchPort(Protocol):
    async def search(self, query: str, *, limit: int) -> list[SearchResult]: ...


class AttioWriterPort(Protocol):
    """Writes the submission and its AI output to Attio and returns what it
    created. Attio first, Postgres second, always — a nightly job overwrites
    Postgres from Attio, so anything written straight to Postgres is
    destroyed on the next run.
    """

    async def write(self, *, tool: Tool, payload: JsonObject, ai: JsonObject) -> SubjectRefs: ...


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
