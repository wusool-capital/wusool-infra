"""Real AWS Bedrock implementation of `BedrockClient`, using the Converse API
for a consistent interface across models. Bounded exponential-backoff retry
on transient errors only — never on validation failures, that's the caller's
job (extraction/reasoning services own the repair-retry-then-fail-closed
policy). Logs metadata only: model id, operation, latency, token usage if
available, success/failure — never raw prompt/response content or credentials.
"""

import asyncio
import json
import logging
import time
from typing import Any

from botocore.exceptions import ClientError, EndpointConnectionError

from app.integrations.bedrock import get_bedrock_runtime_client
from app.modules.llm.domain.bedrock_client import InferenceConfig

logger = logging.getLogger(__name__)

_TRANSIENT_ERROR_CODES = {
    "ThrottlingException",
    "ServiceUnavailableException",
    "ModelTimeoutException",
    "InternalServerException",
}
_MAX_ATTEMPTS = 3
_BASE_DELAY_SECONDS = 1.0


class BedrockInvocationError(Exception):
    """Raised after exhausting retries, or for a non-transient failure. The
    caller must not fabricate output in response — fail closed (§7, §27).
    """


class BedrockConverseClient:
    def __init__(self) -> None:
        self._client = get_bedrock_runtime_client()

    async def generate_structured(
        self, *, model_id: str, prompt: str, inference_config: InferenceConfig
    ) -> dict:
        return await self._invoke(
            model_id=model_id,
            prompt=prompt,
            inference_config=inference_config,
            operation="extraction",
        )

    async def generate_reasoning(
        self, *, model_id: str, prompt: str, inference_config: InferenceConfig
    ) -> dict:
        return await self._invoke(
            model_id=model_id,
            prompt=prompt,
            inference_config=inference_config,
            operation="reasoning",
        )

    async def _invoke(
        self, *, model_id: str, prompt: str, inference_config: InferenceConfig, operation: str
    ) -> dict:
        last_error: Exception | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            started = time.monotonic()
            try:
                response = await asyncio.to_thread(
                    self._converse, model_id, prompt, inference_config
                )
                latency_ms = int((time.monotonic() - started) * 1000)
                usage = response.get("usage", {})
                logger.info(
                    "bedrock_invocation_succeeded",
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
                logger.warning(
                    "bedrock_invocation_failed",
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
        self, model_id: str, prompt: str, inference_config: InferenceConfig
    ) -> dict[str, Any]:
        return self._client.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={
                "temperature": inference_config.temperature,
                "maxTokens": inference_config.max_tokens,
                "topP": inference_config.top_p,
            },
        )

    @staticmethod
    def _extract_json(response: dict[str, Any]) -> dict:
        content = response["output"]["message"]["content"]
        text = "".join(block.get("text", "") for block in content)
        return json.loads(text)
