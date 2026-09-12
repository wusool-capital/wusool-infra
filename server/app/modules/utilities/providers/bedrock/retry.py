"""Shared bounded-retry-with-logging wrapper around one Bedrock `converse`
call. `enrichment`'s and `lead_magnets`' own clients each carried a
byte-identical `_is_retryable`/`_delay_seconds`/`_invoke` scaffolding around
`retry_with_backoff` despite differing in the validation policy layered on
top (single-attempt-raise vs. validate-repair-retry) — this factors out
exactly the identical part, the same reasoning `domain/bedrock.py`'s own
docstring gives for `converse_kwargs`/`extract_json`.

Lives in `providers/`, not `domain/bedrock.py`: this needs
`botocore.exceptions` to classify a retryable failure, and `domain/bedrock.py`
is deliberately framework-free (no boto3/botocore import) so it needs no
`mypy_boto3_bedrock_runtime` typing.

`matching_engine`'s own Bedrock client still hand-rolls its own retry loop,
predating this helper's extraction, with a different call shape
(`InferenceConfig`, not separate `temperature`/`max_tokens`) — left as-is
rather than folded in here, per that module's own docstring ("new callers
should use the shared one, not mirror the older pattern").

Not part of this module's root `__all__` — reached directly
(`app.modules.utilities.providers.bedrock.retry`), same reasoning as
`api/handlers.py`: importing it via the root facade would pull
`botocore`/`mypy_boto3_bedrock_runtime` into every consumer's import graph,
even a `domain/` file that only wants `Money`.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from botocore.exceptions import ClientError, EndpointConnectionError

from app.modules.utilities.domain.bedrock import TRANSIENT_ERROR_CODES, extract_json
from app.modules.utilities.domain.json_types import JsonObject
from app.modules.utilities.domain.provider_errors import BedrockInvocationError
from app.modules.utilities.domain.retry import retry_with_backoff

if TYPE_CHECKING:
    # boto3-stubs is a dev-only type-checking dependency, never installed in
    # the production image — see each caller's own `boto_client.py`.
    from mypy_boto3_bedrock_runtime.type_defs import ConverseResponseTypeDef

logger = logging.getLogger(__name__)


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, EndpointConnectionError):
        return True
    if isinstance(exc, ClientError):
        return exc.response.get("Error", {}).get("Code", "") in TRANSIENT_ERROR_CODES
    return False


async def invoke_bedrock_with_retry(
    *,
    converse: Callable[[], "ConverseResponseTypeDef"],
    model_id: str,
    operation: str,
    max_attempts: int = 3,
    base_delay_seconds: float = 1.0,
) -> JsonObject:
    """Runs `converse()` (a synchronous boto3 call the caller has already
    built, e.g. via `converse_kwargs`) in a thread, retrying up to
    `max_attempts` times total with exponential backoff on a transient AWS
    error only. Logs metadata only (model id, operation, latency, token
    usage — never prompt/response content) on both success and each retry.
    Returns the extracted JSON payload (`extract_json`); raises
    `BedrockInvocationError` if every attempt fails.
    """

    async def call() -> "ConverseResponseTypeDef":
        started = time.monotonic()
        response = await asyncio.to_thread(converse)
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
            max_attempts=max_attempts,
            delay_seconds=lambda attempt: base_delay_seconds * (2 ** (attempt - 1)),
            on_retry=on_retry,
        )
    except (ClientError, EndpointConnectionError) as exc:
        raise BedrockInvocationError(f"{operation} failed: {exc}") from exc

    return extract_json(response)
