"""Bedrock implementation of `LeadLLMPort`, built on Pydantic AI agents over
the Converse API.

Seven operations, two models. What this file owns is which model each
operation uses, its token budget, and its schema. Each run's `output_type`
is a `ToolOutput` with no text output allowed, so Bedrock is forced to call
the output tool and the agent validates the result into the schema.

Validation is a single attempt that raises (`retries={"output": 0}`). The
forced tool call already eliminates most malformed-JSON failure modes, and
unlike `matching_engine` these calls have a visitor waiting: a repair round
trip would cost more latency than the deterministic fallback it is
competing with.

Transient-error retries, metadata-only logging (model id, operation,
latency, token usage — never prompt or response content) and content-free
errors come from the shared `utilities.providers.bedrock.agent`.
"""

from __future__ import annotations

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.bedrock import BedrockModelSettings

from app.modules.lead_magnets.config import get_settings
from app.modules.lead_magnets.domain.shared.schemas import (
    AnalyzeResult,
    CompareResult,
    EnrichResult,
    InternalNote,
    ReadinessResult,
    SearchQueries,
)
from app.modules.lead_magnets.providers.bedrock.boto_client import get_bedrock_runtime_client
from app.modules.utilities.providers.bedrock.agent import (
    bedrock_model,
    run_bedrock_agent,
    structured_agent,
)

# Low and deterministic-leaning: these outputs feed a valuation and a
# readiness score, not prose. `top_p` is never sent alongside it.
_TEMPERATURE = 0.2


class LeadBedrockClient:
    def __init__(self) -> None:
        self._client = get_bedrock_runtime_client()
        settings = get_settings()
        self._sonnet = settings.lead_magnet_model_sonnet
        self._haiku = settings.lead_magnet_model_haiku

    async def enrich(self, *, prompt: str) -> EnrichResult:
        return await self._run(self._sonnet, prompt, EnrichResult, "enrich", max_tokens=1024)

    async def analyze(self, *, prompt: str) -> AnalyzeResult:
        return await self._run(self._sonnet, prompt, AnalyzeResult, "analyze", max_tokens=4096)

    async def plan_search_queries(self, *, prompt: str) -> SearchQueries:
        """Haiku, and queries only — the cheap model handles the throwaway
        work, and letting it name companies produced invented tickers."""
        return await self._run(
            self._haiku, prompt, SearchQueries, "plan_search_queries", max_tokens=512
        )

    async def select_comparables(self, *, prompt: str) -> CompareResult:
        return await self._run(
            self._sonnet, prompt, CompareResult, "select_comparables", max_tokens=4096
        )

    async def score_readiness(self, *, prompt: str) -> ReadinessResult:
        return await self._run(
            self._sonnet, prompt, ReadinessResult, "score_readiness", max_tokens=4096
        )

    async def advise_readiness(self, *, prompt: str) -> InternalNote:
        """The internal advisory note. Haiku: the deterministic rules already
        own the referral and the hard flags, so what is left is one paragraph
        of synthesis."""
        return await self._run(
            self._haiku, prompt, InternalNote, "advise_readiness", max_tokens=1024
        )

    async def qualify_buyer(self, *, prompt: str) -> InternalNote:
        """Internal output only, so a failure here is invisible to the
        applicant — their application is already recorded."""
        return await self._run(self._haiku, prompt, InternalNote, "qualify_buyer", max_tokens=2048)

    async def _run[T: BaseModel](
        self,
        model_id: str,
        prompt: str,
        schema: type[T],
        operation: str,
        *,
        max_tokens: int,
    ) -> T:
        # Built per call: construction is negligible next to a Bedrock round trip.
        agent: Agent[None, T] = structured_agent(schema, name=operation, output_retries=0)
        model = bedrock_model(model_id, self._client)
        settings = BedrockModelSettings(max_tokens=max_tokens, temperature=_TEMPERATURE)
        return await run_bedrock_agent(
            lambda: agent.run(prompt, model=model, model_settings=settings),
            model_id=model_id,
            operation=operation,
        )
