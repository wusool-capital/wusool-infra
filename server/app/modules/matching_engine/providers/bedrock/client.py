"""Real AWS Bedrock implementation of `BedrockClient`, using the Converse API
for a consistent interface across models. Bounded exponential-backoff retry
on transient errors only (`_invoke`) — a separate concern from the
validate-repair-retry-then-fail-closed policy `extract_requirements`/
`generate_reasoning` each own for their own vendor-response schema
(`schemas.py`). Logs metadata only: model id, operation, latency, token
usage if available, success/failure — never raw prompt/response content or
credentials.
"""

import asyncio
import json
import logging
import re
import time
from typing import Any

from botocore.exceptions import ClientError, EndpointConnectionError
from pydantic import ValidationError

from app.modules.matching_engine.application.ports.llm import RepairPromptBuilder
from app.modules.matching_engine.application.ports.llm_types import InferenceConfig
from app.modules.matching_engine.application.provider_errors import BedrockInvocationError
from app.modules.matching_engine.domain.matching.scoring import is_monetary_criterion
from app.modules.matching_engine.providers.bedrock.boto_client import get_bedrock_runtime_client
from app.modules.matching_engine.providers.bedrock.schemas import (
    ExtractedRequirementProfile,
    ReasoningResult,
)
from app.modules.utilities.domain.money import parse_usd_amount

logger = logging.getLogger(__name__)

_TRANSIENT_ERROR_CODES = {
    "ThrottlingException",
    "ServiceUnavailableException",
    "ModelTimeoutException",
    "InternalServerException",
}
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
    ) -> dict:
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
    def _validate_extraction(raw: dict) -> tuple[dict | None, str | None]:
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
    ) -> dict:
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
    def _validate_reasoning(raw: dict) -> tuple[dict | None, str | None]:
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
        output_schema: dict,
        operation: str,
    ) -> dict:
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
                return self._extract_json(response)
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
                if error_code not in _TRANSIENT_ERROR_CODES or attempt == _MAX_ATTEMPTS:
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
        output_schema: dict,
    ) -> dict[str, Any]:
        # Anthropic models reject `temperature` and `top_p` set together
        # (confirmed live: Bedrock raises ValidationException) — Anthropic's
        # own guidance is to tune one or the other, never both. `temperature`
        # wins since a low, deterministic-leaning value is what extraction/
        # reasoning actually wants here; `top_p` stays configured but unused
        # unless a future need calls for switching the sampling strategy.
        return self._client.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={
                "temperature": inference_config.temperature,
                "maxTokens": inference_config.max_tokens,
            },
            toolConfig={
                "tools": [
                    {
                        "toolSpec": {
                            "name": "return_structured_output",
                            "description": (
                                "Return the result as structured JSON matching the given schema."
                            ),
                            "inputSchema": {"json": output_schema},
                        }
                    }
                ],
                # Forces the model to emit its answer as this tool's parsed
                # JSON input instead of free text — removes the root cause of
                # the markdown-fence/prose-wrapping failure mode entirely,
                # rather than recovering from it after the fact.
                "toolChoice": {"tool": {"name": "return_structured_output"}},
            },
        )

    @staticmethod
    def _extract_json(response: dict[str, Any]) -> dict:
        """Prefers the forced tool call's already-parsed JSON input. Falls
        back to text extraction only if a model/profile ignores the forced
        tool choice (confirmed live: some models routinely wrap JSON in a
        ```json fence and add prose commentary despite being asked for
        strict JSON, or being forced via toolConfig) — best-effort recovery
        (direct parse, then fenced block, then the first balanced {...}
        substring) keeps that this class's own repair-retry's problem to
        handle uniformly (§7): returning `{}` on total failure fails
        Pydantic validation the same way a wrong-shaped-but-valid JSON
        object would, rather than raising a second, differently-shaped
        error here.
        """
        content = response["output"]["message"]["content"]

        for block in content:
            tool_use = block.get("toolUse")
            if tool_use and isinstance(tool_use.get("input"), dict):
                return tool_use["input"]

        text = "".join(block.get("text", "") for block in content).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if fenced:
            try:
                return json.loads(fenced.group(1))
            except json.JSONDecodeError:
                pass

        start = text.find("{")
        if start != -1:
            depth = 0
            for i, ch in enumerate(text[start:], start=start):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start : i + 1])
                        except json.JSONDecodeError:
                            break

        return {}
