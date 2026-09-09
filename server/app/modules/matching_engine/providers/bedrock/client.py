"""Real AWS Bedrock implementation of `BedrockClient`, using the Converse API
for a consistent interface across models. Bounded exponential-backoff retry
on transient errors only (`_invoke`) — a separate concern from the
validate-repair-retry-then-fail-closed policy `extract_requirements`/
`generate_reasoning` each own for their own vendor-response schema
(`schemas.py`). Logs metadata only: model id, operation, latency, token
usage if available, success/failure — never raw prompt/response content or
credentials.

The response parsing, transient-error set and `converse` request shape are
shared with every other Bedrock caller in
`app.modules.utilities.domain.bedrock`; this file owns only what is genuinely
its own — the retry loop and the repair-retry validation policy above.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from botocore.exceptions import ClientError, EndpointConnectionError
from pydantic import ValidationError

from app.modules.matching_engine.application.ports.llm import RepairPromptBuilder
from app.modules.matching_engine.application.ports.llm_types import InferenceConfig
from app.modules.matching_engine.domain.matching.scoring import is_monetary_criterion
from app.modules.matching_engine.providers.bedrock.boto_client import get_bedrock_runtime_client
from app.modules.matching_engine.providers.bedrock.schemas import (
    ExtractedRequirementProfile,
    ReasoningResult,
)
from app.modules.utilities.domain.bedrock import (
    TRANSIENT_ERROR_CODES,
    converse_kwargs,
    extract_json,
)
from app.modules.utilities.domain.json_types import JsonObject, JsonSchema
from app.modules.utilities.domain.money import parse_usd_amount
from app.modules.utilities.domain.provider_errors import BedrockInvocationError

if TYPE_CHECKING:
    # boto3-stubs is a dev-only type-checking dependency (see pyproject.toml)
    # — never installed in the production image, so this import must stay
    # inside TYPE_CHECKING (and `from __future__ import annotations` above
    # keeps the annotations below from being evaluated at runtime).
    from mypy_boto3_bedrock_runtime.type_defs import ConverseResponseTypeDef

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3
_BASE_DELAY_SECONDS = 1.0


class BedrockConverseClient:
    def __init__(self) -> None:
        self._client = get_bedrock_runtime_client()

    async def extract_requirements(
        self,
        *,
        model_id: str,
        prompt: str,
        repair_prompt_builder: RepairPromptBuilder,
        inference_config: InferenceConfig,
    ) -> JsonObject:
        output_schema = ExtractedRequirementProfile.model_json_schema()
        raw = await self._invoke(
            model_id=model_id,
            prompt=prompt,
            inference_config=inference_config,
            output_schema=output_schema,
            operation="extraction",
        )
        validated, error = self._validate_extraction(raw)

        if validated is None:
            raw_retry = await self._invoke(
                model_id=model_id,
                prompt=repair_prompt_builder(raw, error or ""),
                inference_config=inference_config,
                output_schema=output_schema,
                operation="extraction",
            )
            validated, error = self._validate_extraction(raw_retry)

        if validated is None:
            raise BedrockInvocationError(
                f"extraction output failed validation after one repair attempt: {error}"
            )
        return validated

    @staticmethod
    def _validate_extraction(raw: JsonObject) -> tuple[JsonObject | None, str | None]:
        try:
            extracted = ExtractedRequirementProfile.model_validate(raw)
            for requirement in [*extracted.hard_requirements, *extracted.soft_preferences]:
                if is_monetary_criterion(requirement.criterion) and requirement.value is not None:
                    parse_usd_amount(requirement.value)
            return extracted.model_dump(), None
        except (ValidationError, ValueError) as exc:
            return None, str(exc)

    async def generate_reasoning(
        self,
        *,
        model_id: str,
        prompt: str,
        repair_prompt_builder: RepairPromptBuilder,
        inference_config: InferenceConfig,
    ) -> JsonObject:
        output_schema = ReasoningResult.model_json_schema()
        raw = await self._invoke(
            model_id=model_id,
            prompt=prompt,
            inference_config=inference_config,
            output_schema=output_schema,
            operation="reasoning",
        )
        validated, error = self._validate_reasoning(raw)

        if validated is None:
            raw_retry = await self._invoke(
                model_id=model_id,
                prompt=repair_prompt_builder(raw, error or ""),
                inference_config=inference_config,
                output_schema=output_schema,
                operation="reasoning",
            )
            validated, error = self._validate_reasoning(raw_retry)

        if validated is None:
            raise BedrockInvocationError(
                f"reasoning output failed validation after one repair attempt: {error}"
            )
        return validated

    @staticmethod
    def _validate_reasoning(raw: JsonObject) -> tuple[JsonObject | None, str | None]:
        try:
            return ReasoningResult.model_validate(raw).model_dump(), None
        except ValidationError as exc:
            return None, str(exc)

    async def _invoke(
        self,
        *,
        model_id: str,
        prompt: str,
        inference_config: InferenceConfig,
        output_schema: JsonSchema,
        operation: str,
    ) -> JsonObject:
        last_error: Exception | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            started = time.monotonic()
            try:
                response = await asyncio.to_thread(
                    self._converse, model_id, prompt, inference_config, output_schema
                )
                latency_ms = int((time.monotonic() - started) * 1000)
                usage = response.get("usage", {})
                logger.info(
                    "bedrock_invocation_succeeded operation=%s model_id=%s attempt=%d "
                    "latency_ms=%d input_tokens=%s output_tokens=%s",
                    operation,
                    model_id,
                    attempt,
                    latency_ms,
                    usage.get("inputTokens"),
                    usage.get("outputTokens"),
                    extra={
                        "model_id": model_id,
                        "operation": operation,
                        "latency_ms": latency_ms,
                        "input_tokens": usage.get("inputTokens"),
                        "output_tokens": usage.get("outputTokens"),
                        "attempt": attempt,
                    },
                )
                return extract_json(response)
            except ClientError as exc:
                last_error = exc
                error_code = exc.response.get("Error", {}).get("Code", "")
                error_message = exc.response.get("Error", {}).get("Message", "")
                logger.warning(
                    "bedrock_invocation_failed operation=%s model_id=%s attempt=%d "
                    "error_code=%s error_message=%s",
                    operation,
                    model_id,
                    attempt,
                    error_code,
                    error_message,
                    extra={
                        "model_id": model_id,
                        "operation": operation,
                        "latency_ms": int((time.monotonic() - started) * 1000),
                        "error_code": error_code,
                        "attempt": attempt,
                    },
                )
                if error_code not in TRANSIENT_ERROR_CODES or attempt == _MAX_ATTEMPTS:
                    raise BedrockInvocationError(f"{operation} failed: {error_code}") from exc
                await asyncio.sleep(_BASE_DELAY_SECONDS * (2 ** (attempt - 1)))
            except EndpointConnectionError as exc:
                last_error = exc
                if attempt == _MAX_ATTEMPTS:
                    raise BedrockInvocationError(f"{operation} failed: connection error") from exc
                await asyncio.sleep(_BASE_DELAY_SECONDS * (2 ** (attempt - 1)))
        raise BedrockInvocationError(
            f"{operation} failed after {_MAX_ATTEMPTS} attempts"
        ) from last_error

    def _converse(
        self,
        model_id: str,
        prompt: str,
        inference_config: InferenceConfig,
        output_schema: JsonSchema,
    ) -> ConverseResponseTypeDef:
        # No `system` block: this module's prompts are entirely user-turn.
        # `top_p` stays configured but unused — see `converse_kwargs`.
        return self._client.converse(
            **converse_kwargs(
                model_id=model_id,
                prompt=prompt,
                output_schema=output_schema,
                max_tokens=inference_config.max_tokens,
                temperature=inference_config.temperature,
            )
        )
