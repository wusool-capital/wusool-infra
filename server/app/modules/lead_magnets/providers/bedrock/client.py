"""Bedrock implementation of `LeadLLMPort`.

Six operations, two models. The transport — the `converse` request shape,
the transient-error set and the response parsing — is shared with every
other Bedrock caller in `utilities.domain.bedrock`; what this file owns is
which model each operation uses, its token budget, and its schema.

Validation is a single attempt that raises. The forced tool call already
eliminates most malformed-JSON failure modes, and unlike `matching_engine`
these calls have a visitor waiting: a repair round trip would cost more
latency than the deterministic fallback it is competing with.

Logs metadata only — model id, operation, latency, token usage — never raw
prompt or response content.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, TypeVar

from botocore.exceptions import ClientError, EndpointConnectionError
from pydantic import BaseModel, ValidationError

from app.modules.lead_magnets.config import get_settings
from app.modules.lead_magnets.providers.bedrock.boto_client import get_bedrock_runtime_client
from app.modules.lead_magnets.providers.bedrock.schemas import (
    AnalyzeResult,
    CompareResult,
    EnrichResult,
    InternalNote,
    ReadinessResult,
    SearchQueries,
)
from app.modules.utilities import retry_with_backoff
from app.modules.utilities.domain.bedrock import (
    TRANSIENT_ERROR_CODES,
    converse_kwargs,
    extract_json,
)
from app.modules.utilities.domain.json_types import JsonObject
from app.modules.utilities.domain.provider_errors import BedrockInvocationError

if TYPE_CHECKING:
    from mypy_boto3_bedrock_runtime.type_defs import ConverseResponseTypeDef

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3
_BASE_DELAY_SECONDS = 1.0
# Low and deterministic-leaning: these outputs feed a valuation and a
# readiness score, not prose. `top_p` is never sent alongside it — Anthropic
# models reject both together.
_TEMPERATURE = 0.2

ModelT = TypeVar("ModelT", bound=BaseModel)


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, EndpointConnectionError):
        return True
    if isinstance(exc, ClientError):
        return exc.response.get("Error", {}).get("Code", "") in TRANSIENT_ERROR_CODES
    return False


def _delay_seconds(attempt: int) -> float:
    return _BASE_DELAY_SECONDS * (2 ** (attempt - 1))


class LeadBedrockClient:
    def __init__(self) -> None:
        self._client = get_bedrock_runtime_client()
        settings = get_settings()
        self._sonnet = settings.lead_magnet_model_sonnet
        self._haiku = settings.lead_magnet_model_haiku

    async def enrich(self, *, prompt: str) -> JsonObject:
        return await self._invoke(self._sonnet, prompt, EnrichResult, "enrich", max_tokens=1024)

    async def analyze(self, *, prompt: str) -> JsonObject:
        return await self._invoke(self._sonnet, prompt, AnalyzeResult, "analyze", max_tokens=4096)

    async def plan_search_queries(self, *, prompt: str) -> JsonObject:
        """Haiku, and queries only — the cheap model handles the throwaway
        work, and letting it name companies produced invented tickers."""
        return await self._invoke(
            self._haiku, prompt, SearchQueries, "plan_search_queries", max_tokens=512
        )

    async def select_comparables(self, *, prompt: str) -> JsonObject:
        return await self._invoke(
            self._sonnet, prompt, CompareResult, "select_comparables", max_tokens=4096
        )

    async def score_readiness(self, *, prompt: str) -> JsonObject:
        return await self._invoke(
            self._sonnet, prompt, ReadinessResult, "score_readiness", max_tokens=4096
        )

    async def advise_readiness(self, *, prompt: str) -> JsonObject:
        """The internal advisory note. Haiku: the deterministic rules already
        own the referral and the hard flags, so what is left is one paragraph
        of synthesis."""
        return await self._invoke(
            self._haiku, prompt, InternalNote, "advise_readiness", max_tokens=1024
        )

    async def qualify_buyer(self, *, prompt: str) -> JsonObject:
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
    ) -> JsonObject:
        output_schema = response_model.model_json_schema()

        async def call() -> ConverseResponseTypeDef:
            started = time.monotonic()
            response = await asyncio.to_thread(
                self._converse, model_id, prompt, output_schema, max_tokens
            )
            latency_ms = int((time.monotonic() - started) * 1000)
            usage = response.get("usage", {})
            logger.info(
                "bedrock_invocation_succeeded operation=%s model_id=%s latency_ms=%d "
                "input_tokens=%s output_tokens=%s",
                operation,
                model_id,
                latency_ms,
                usage.get("inputTokens"),
                usage.get("outputTokens"),
                extra={
                    "model_id": model_id,
                    "operation": operation,
                    "latency_ms": latency_ms,
                    "input_tokens": usage.get("inputTokens"),
                    "output_tokens": usage.get("outputTokens"),
                },
            )
            return response

        def on_retry(attempt: int, exc: Exception, delay: float) -> None:
            error_code = (
                exc.response.get("Error", {}).get("Code", "")
                if isinstance(exc, ClientError)
                else "EndpointConnectionError"
            )
            logger.warning(
                "bedrock_invocation_failed operation=%s model_id=%s attempt=%d error_code=%s",
                operation,
                model_id,
                attempt,
                error_code,
                extra={
                    "model_id": model_id,
                    "operation": operation,
                    "attempt": attempt,
                    "error_code": error_code,
                },
            )

        try:
            response = await retry_with_backoff(
                call,
                is_retryable=_is_retryable,
                max_attempts=_MAX_ATTEMPTS,
                delay_seconds=_delay_seconds,
                on_retry=on_retry,
            )
        except (ClientError, EndpointConnectionError) as exc:
            raise BedrockInvocationError(f"{operation} failed: {exc}") from exc

        raw = extract_json(response)
        try:
            return response_model.model_validate(raw).model_dump()
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
