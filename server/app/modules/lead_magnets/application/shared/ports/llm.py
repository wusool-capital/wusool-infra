"""The Bedrock seam. Faked in tests, implemented by
`providers/bedrock/client.py`."""

from typing import Protocol

from app.modules.lead_magnets.domain.shared.schemas import (
    AnalyzeResult,
    CompareResult,
    EnrichResult,
    InternalNote,
    ReadinessResult,
    SearchQueries,
)


class LeadLLMPort(Protocol):
    """One method per model call, named for the operation rather than the
    schema — the same shape `meetings.SummarizerLLM` and
    `matching_engine.BedrockClient` use.

    Each takes a finished prompt: prompts are pure functions in `domain/`,
    so this layer never learns a model id, a token budget or a response
    schema. Each returns an already-validated Pydantic model — these are
    `domain/shared/schemas.py` types, the one place `application/` is
    allowed to see `pydantic` model instances (never the `pydantic` import
    itself), since a real implementation validates the model's raw output
    before handing it here.
    """

    async def enrich(self, *, prompt: str) -> EnrichResult: ...

    async def analyze(self, *, prompt: str) -> AnalyzeResult: ...

    async def plan_search_queries(self, *, prompt: str) -> SearchQueries: ...

    async def select_comparables(self, *, prompt: str) -> CompareResult: ...

    async def score_readiness(self, *, prompt: str) -> ReadinessResult: ...

    async def advise_readiness(self, *, prompt: str) -> InternalNote: ...

    async def qualify_buyer(self, *, prompt: str) -> InternalNote: ...
