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
from app.modules.utilities.domain.json_types import JsonObject


class LeadLLMPort(Protocol):
    """One method per model call, named for the operation rather than the
    schema — the same shape `meetings.SummarizerLLM` and
    `matching_engine.BedrockClient` use.

    Each takes a finished prompt: prompts are pure functions in `domain/`,
    so this layer never learns a model id, a token budget or a response
    schema. Each returns an already-validated plain `dict`; Pydantic models
    must not cross this seam.
    """

    async def enrich(self, *, prompt: str) -> JsonObject: ...

    async def analyze(self, *, prompt: str) -> JsonObject: ...

    async def plan_search_queries(self, *, prompt: str) -> JsonObject: ...

    async def select_comparables(self, *, prompt: str) -> JsonObject: ...

    async def score_readiness(self, *, prompt: str) -> JsonObject: ...

    async def advise_readiness(self, *, prompt: str) -> JsonObject: ...

    async def qualify_buyer(self, *, prompt: str) -> JsonObject: ...


class SearchPort(Protocol):
    async def search(self, query: str, *, limit: int) -> list[SearchResult]: ...

    async def scrape(self, url: str) -> str:
        """The page's text, or `""` if it could not be fetched.

        `/enrich` reads the one URL the visitor gave us, so there is nothing
        to search for — the live prompt's "use web search to find the
        company's website" was solving a problem that does not exist here.
        """
        ...


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
