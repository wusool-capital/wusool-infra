"""Real AWS Bedrock implementation of `SummarizerLLM`, using the Converse
API. Retries transient errors only (`app.modules.utilities.retry_with_backoff`).

Unlike matching_engine's client, validation here is a single attempt that
raises on failure rather than a validate-repair-retry-then-fail-closed
dance: the forced tool call already eliminates most malformed-JSON failure
modes, so the extra repair-prompt round trip matching_engine's extraction/
reasoning methods need for their own vendor schemas isn't needed here.

Still its OWN client, for one remaining reason: a 300s `read_timeout`
(botocore's 60s default is too short for a whole-meeting summarization
call, per Scribe's own production incident this port fixed). The response
parsing, the transient-error set and the `converse` request shape are no
longer duplicated — they live in `app.modules.utilities.domain.bedrock`,
shared with `matching_engine` and any other caller, so a fix lands once.

Logs metadata only: model id, operation, latency, token usage if available,
success/failure — never raw prompt/response content or credentials.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from botocore.exceptions import ClientError, EndpointConnectionError
from pydantic import ValidationError

from app.modules.meetings.providers.bedrock.boto_client import get_bedrock_runtime_client
from app.modules.meetings.providers.bedrock.schemas import MeetingSummarySchema
from app.modules.utilities import retry_with_backoff
from app.modules.utilities.domain.bedrock import (
    TRANSIENT_ERROR_CODES,
    converse_kwargs,
    extract_json,
)
from app.modules.utilities.domain.json_types import JsonObject
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
_OPERATION = "summarization"


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

        raw = extract_json(response)
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
        return self._client.converse(
            **converse_kwargs(
                model_id=model_id,
                prompt=prompt,
                output_schema=output_schema,
                max_tokens=max_tokens,
                temperature=temperature,
                system_prompt=system_prompt,
            )
        )
