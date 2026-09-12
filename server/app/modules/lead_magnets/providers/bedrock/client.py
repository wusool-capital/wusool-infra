"""Bedrock implementation of `LeadLLMPort`.

Six operations, two models. The transport — the `converse` request shape,
the transient-error set, the response parsing, and the entire
retry-with-logging wrapper are shared with every other Bedrock caller via
`utilities.domain.bedrock`/`utilities.providers.bedrock.retry`; what this
file owns is which model each operation uses, its token budget, and its
schema.

Validation is a single attempt that raises. The forced tool call already
eliminates most malformed-JSON failure modes, and unlike `matching_engine`
these calls have a visitor waiting: a repair round trip would cost more
latency than the deterministic fallback it is competing with.

Logs metadata only — model id, operation, latency, token usage — never raw
prompt or response content.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from pydantic import BaseModel, ValidationError

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
from app.modules.utilities.domain.bedrock import converse_kwargs
from app.modules.utilities.domain.json_types import JsonObject
from app.modules.utilities.domain.provider_errors import BedrockInvocationError
from app.modules.utilities.providers.bedrock.retry import invoke_bedrock_with_retry

if TYPE_CHECKING:
    from mypy_boto3_bedrock_runtime.type_defs import ConverseResponseTypeDef

# Low and deterministic-leaning: these outputs feed a valuation and a
# readiness score, not prose. `top_p` is never sent alongside it — Anthropic
# models reject both together.
_TEMPERATURE = 0.2

ModelT = TypeVar("ModelT", bound=BaseModel)


class LeadBedrockClient:
    def __init__(self) -> None:
        self._client = get_bedrock_runtime_client()
        settings = get_settings()
        self._sonnet = settings.lead_magnet_model_sonnet
        self._haiku = settings.lead_magnet_model_haiku

    async def enrich(self, *, prompt: str) -> EnrichResult:
        return await self._invoke(self._sonnet, prompt, EnrichResult, "enrich", max_tokens=1024)

    async def analyze(self, *, prompt: str) -> AnalyzeResult:
        return await self._invoke(self._sonnet, prompt, AnalyzeResult, "analyze", max_tokens=4096)

    async def plan_search_queries(self, *, prompt: str) -> SearchQueries:
        """Haiku, and queries only — the cheap model handles the throwaway
        work, and letting it name companies produced invented tickers."""
        return await self._invoke(
            self._haiku, prompt, SearchQueries, "plan_search_queries", max_tokens=512
        )

    async def select_comparables(self, *, prompt: str) -> CompareResult:
        return await self._invoke(
            self._sonnet, prompt, CompareResult, "select_comparables", max_tokens=4096
        )

    async def score_readiness(self, *, prompt: str) -> ReadinessResult:
        return await self._invoke(
            self._sonnet, prompt, ReadinessResult, "score_readiness", max_tokens=4096
        )

    async def advise_readiness(self, *, prompt: str) -> InternalNote:
        """The internal advisory note. Haiku: the deterministic rules already
        own the referral and the hard flags, so what is left is one paragraph
        of synthesis."""
        return await self._invoke(
            self._haiku, prompt, InternalNote, "advise_readiness", max_tokens=1024
        )

    async def qualify_buyer(self, *, prompt: str) -> InternalNote:
        """Internal output only, so a failure here is invisible to the
        applicant — their application is already recorded."""
        return await self._invoke(
            self._haiku, prompt, InternalNote, "qualify_buyer", max_tokens=2048
        )

    async def _invoke(
        self,
        model_id: str,
        prompt: str,
        response_model: type[ModelT],
        operation: str,
        *,
        max_tokens: int,
    ) -> ModelT:
        output_schema = response_model.model_json_schema()

        raw = await invoke_bedrock_with_retry(
            converse=lambda: self._converse(model_id, prompt, output_schema, max_tokens),
            model_id=model_id,
            operation=operation,
        )
        try:
            return response_model.model_validate(raw)
        except ValidationError as exc:
            # NOT f"...: {exc}" — pydantic's ValidationError.__str__ embeds
            # each failing field's `input_value`, which here is the model's
            # own output about a real visitor's company. That would land in
            # a log line and in `tool_runs.error`. Field path and error type
            # only, never the value.
            field_errors = "; ".join(
                f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}"
                for err in exc.errors()
            )
            raise BedrockInvocationError(
                f"{operation} output failed validation: {field_errors}"
            ) from exc

    def _converse(
        self, model_id: str, prompt: str, output_schema: JsonObject, max_tokens: int
    ) -> ConverseResponseTypeDef:
        return self._client.converse(
            **converse_kwargs(
                model_id=model_id,
                prompt=prompt,
                output_schema=output_schema,
                max_tokens=max_tokens,
                temperature=_TEMPERATURE,
            )
        )
