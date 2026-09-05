"""Real AWS Bedrock implementation of `SummarizerLLM`, using the Converse
API. Retries transient errors only (`app.modules.utilities.retry_with_backoff`).

Unlike matching_engine's client, validation here is a single attempt that
raises on failure rather than a validate-repair-retry-then-fail-closed
dance: the forced tool call already eliminates most malformed-JSON failure
modes, so the extra repair-prompt round trip matching_engine's extraction/
reasoning methods need for their own vendor schemas isn't needed here.

Deliberately its OWN client, not a shared one with `matching_engine`'s
`providers/bedrock/client.py` — two concrete differences forced that: this
module needs a `system` prompt block (matching_engine's `_converse` never
sends one) and a 300s `read_timeout` (matching_engine's
`get_bedrock_runtime_client` is `@lru_cache`d with no `Config`, i.e.
botocore's 60s default — too short for a whole-meeting summarization call,
per Scribe's own production incident this port is fixing). `_extract_json`
below and the transient-error-code set in this file are near-duplicates of
matching_engine's as a result. Extracting that shared plumbing into
`utilities/providers/` is a deliberate follow-up, not an oversight —
refactoring a live, tested `matching_engine` path for a module that hadn't
shipped yet was judged the wrong order for this PR (see the module README).
If you're fixing a bug in `_extract_json`/the retry policy here, check
whether `matching_engine`'s copy has the same bug.

Logs metadata only: model id, operation, latency, token usage if available,
success/failure — never raw prompt/response content or credentials.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import TYPE_CHECKING, Any

from botocore.exceptions import ClientError, EndpointConnectionError
from pydantic import ValidationError

from app.modules.meetings.providers.bedrock.boto_client import get_bedrock_runtime_client
from app.modules.meetings.providers.bedrock.schemas import MeetingSummarySchema
from app.modules.utilities import retry_with_backoff
from app.modules.utilities.domain.json_types import JsonObject
from app.modules.utilities.domain.provider_errors import BedrockInvocationError

if TYPE_CHECKING:
    # boto3-stubs is a dev-only type-checking dependency (see pyproject.toml)
    # — never installed in the production image, so this import must stay
    # inside TYPE_CHECKING (and `from __future__ import annotations` above
    # keeps the annotations below from being evaluated at runtime).
    from mypy_boto3_bedrock_runtime.type_defs import ConverseResponseTypeDef

logger = logging.getLogger(__name__)

_TRANSIENT_ERROR_CODES = {
    "ThrottlingException",
    "ServiceUnavailableException",
    "ModelTimeoutException",
    "InternalServerException",
}
_MAX_ATTEMPTS = 3
_BASE_DELAY_SECONDS = 1.0
_OPERATION = "summarization"


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, EndpointConnectionError):
        return True
    if isinstance(exc, ClientError):
        return exc.response.get("Error", {}).get("Code", "") in _TRANSIENT_ERROR_CODES
    return False


def _delay_seconds(attempt: int) -> float:
    return _BASE_DELAY_SECONDS * (2 ** (attempt - 1))


class BedrockConverseClient:
    def __init__(self) -> None:
        self._client = get_bedrock_runtime_client()

    async def summarize(
        self,
        *,
        model_id: str,
        prompt: str,
        system_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> JsonObject:
        output_schema = MeetingSummarySchema.model_json_schema()

        async def call() -> ConverseResponseTypeDef:
            started = time.monotonic()
            response = await asyncio.to_thread(
                self._converse,
                model_id,
                prompt,
                system_prompt,
                max_tokens,
                temperature,
                output_schema,
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

        raw = self._extract_json(response)
        try:
            return MeetingSummarySchema.model_validate(raw).model_dump()
        except ValidationError as exc:
            # NOT f"...: {exc}" — pydantic's ValidationError.__str__ embeds
            # each failing field's `input_value`, which here is the LLM's
            # own (transcript-derived) raw output. That would leak into
            # this exception's message, and from there into a log line and
            # `meetings.metadata_.failure_reason` (see mark_failed) —
            # exactly the raw-response content this file's own docstring
            # promises never to log. Report the field path and error type
            # only, never the value.
            field_errors = "; ".join(
                f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}"
                for err in exc.errors()
            )
            raise BedrockInvocationError(
                f"{_OPERATION} output failed validation: {field_errors}"
            ) from exc

    def _converse(
        self,
        model_id: str,
        prompt: str,
        system_prompt: str,
        max_tokens: int,
        temperature: float,
        output_schema: JsonObject,
    ) -> ConverseResponseTypeDef:
        kwargs: dict[str, Any] = {
            "modelId": model_id,
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            # Anthropic models reject `temperature` and `top_p` set together
            # (confirmed live: Bedrock raises ValidationException) —
            # Anthropic's own guidance is to tune one or the other, never
            # both. `temperature` wins since a low, deterministic-leaning
            # value is what summarization wants here.
            "inferenceConfig": {"temperature": temperature, "maxTokens": max_tokens},
            "toolConfig": {
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
        }
        if system_prompt:
            kwargs["system"] = [{"text": system_prompt}]
        return self._client.converse(**kwargs)

    @staticmethod
    def _extract_json(response: ConverseResponseTypeDef) -> JsonObject:
        """Prefers the forced tool call's already-parsed JSON input. Falls
        back to text extraction only if a model/profile ignores the forced
        tool choice (confirmed live: some models routinely wrap JSON in a
        ```json fence and add prose commentary despite being asked for
        strict JSON, or being forced via toolConfig) — best-effort recovery
        (direct parse, then fenced block, then the first balanced {...}
        substring) keeps that this class's own single-validation-attempt's
        problem to handle uniformly: returning `{}` on total failure fails
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
