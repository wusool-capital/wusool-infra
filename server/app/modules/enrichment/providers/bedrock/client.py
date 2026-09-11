"""Real AWS Bedrock implementation of `ExtractionClient`, using the Converse
API. Mirrors `matching_engine.providers.bedrock.client.BedrockConverseClient`'s
validate -> repair-prompt retry -> fail-closed policy, narrowed to this
module's single extraction operation.

The `converse` request shape, response parsing, and transient-error set are
shared with every other Bedrock caller via `utilities.domain.bedrock`, and
the bounded-retry loop itself via `utilities.retry_with_backoff` — same as
`meetings`'/`lead_magnets`' own clients (`matching_engine`'s still
hand-rolls its own loop, predating that helper's extraction; new callers
should use the shared one, not mirror the older pattern). This file owns
only what's genuinely its own: the repair-retry validation policy above the
retry loop, and the `is_retryable`/`delay` policy functions it passes in.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from botocore.exceptions import ClientError, EndpointConnectionError
from pydantic import ValidationError

from app.modules.enrichment.application.ports.llm import RepairPromptBuilder
from app.modules.enrichment.providers.bedrock.boto_client import get_bedrock_runtime_client
from app.modules.enrichment.providers.bedrock.schemas import ExtractedFields
from app.modules.utilities import BedrockInvocationError, retry_with_backoff
from app.modules.utilities.domain.bedrock import (
    TRANSIENT_ERROR_CODES,
    converse_kwargs,
    extract_json,
)
from app.modules.utilities.domain.json_types import JsonObject

if TYPE_CHECKING:
    from mypy_boto3_bedrock_runtime.type_defs import ConverseResponseTypeDef

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3
_BASE_DELAY_SECONDS = 1.0
_OPERATION = "enrichment_extraction"


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, EndpointConnectionError):
        return True
    if isinstance(exc, ClientError):
        return exc.response.get("Error", {}).get("Code", "") in TRANSIENT_ERROR_CODES
    return False


def _delay_seconds(attempt: int) -> float:
    return _BASE_DELAY_SECONDS * (2 ** (attempt - 1))


class BedrockConverseClient:
    def __init__(self) -> None:
        self._client = get_bedrock_runtime_client()

    async def extract_fields(
        self,
        *,
        model_id: str,
        prompt: str,
        repair_prompt_builder: RepairPromptBuilder,
        temperature: float,
        max_tokens: int,
    ) -> JsonObject:
        output_schema = ExtractedFields.model_json_schema()
        raw = await self._invoke(model_id, prompt, temperature, max_tokens, output_schema)
        validated, error = self._validate(raw)

        if validated is None:
            raw_retry = await self._invoke(
                model_id,
                repair_prompt_builder(raw, error or ""),
                temperature,
                max_tokens,
                output_schema,
            )
            validated, error = self._validate(raw_retry)

        if validated is None:
            raise BedrockInvocationError(
                f"enrichment extraction failed validation after one repair attempt: {error}"
            )
        return validated

    @staticmethod
    def _validate(raw: JsonObject) -> tuple[JsonObject | None, str | None]:
        try:
            return ExtractedFields.model_validate(raw).model_dump(), None
        except ValidationError as exc:
            return None, str(exc)

    async def _invoke(
        self,
        model_id: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
        output_schema: JsonObject,
    ) -> JsonObject:
        """Bounded exponential-backoff retry on transient AWS errors only —
        a separate concern from the validate-repair-retry policy above,
        which retries on a *schema* failure with a different prompt.
        """

        async def call() -> ConverseResponseTypeDef:
            started = time.monotonic()
            response = await asyncio.to_thread(
                self._converse, model_id, prompt, temperature, max_tokens, output_schema
            )
            latency_ms = int((time.monotonic() - started) * 1000)
            usage = response.get("usage", {})
            logger.info(
                "bedrock_invocation_succeeded operation=%s model_id=%s latency_ms=%d "
                "input_tokens=%s output_tokens=%s",
                _OPERATION,
                model_id,
                latency_ms,
                usage.get("inputTokens"),
                usage.get("outputTokens"),
                extra={
                    "model_id": model_id,
                    "operation": _OPERATION,
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
                _OPERATION,
                model_id,
                attempt,
                error_code,
                extra={
                    "model_id": model_id,
                    "operation": _OPERATION,
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
            raise BedrockInvocationError(f"{_OPERATION} failed: {exc}") from exc

        return extract_json(response)

    def _converse(
        self,
        model_id: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
        output_schema: JsonObject,
    ) -> ConverseResponseTypeDef:
        return self._client.converse(
            **converse_kwargs(
                model_id=model_id,
                prompt=prompt,
                output_schema=output_schema,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        )
