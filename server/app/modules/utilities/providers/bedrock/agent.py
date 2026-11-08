"""Shared runner for Pydantic AI agents on Bedrock, used by every module's
Bedrock client.

Each client builds its agents with `structured_agent` (its schema as the only
output, so Bedrock is forced to answer through the output tool and the agent
validates the result) and hands one run to `run_bedrock_agent`. This module
owns what is identical across them:

- transient AWS errors (`TRANSIENT_ERROR_CODES`, connection failures) are
  retried around the whole run with exponential backoff and a warning per
  attempt. botocore's own retry modes skip `ModelTimeoutException`;
- logs carry metadata only: model id, operation, latency, tokens, requests;
- Pydantic AI errors can embed model output, so they are replaced with a
  `BedrockInvocationError` naming the operation and error code, not chained.

Reached directly (`app.modules.utilities.providers.bedrock.agent`), not via
the root facade, so `domain/` consumers never import pydantic_ai or botocore.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from pydantic import BaseModel
from pydantic_ai import Agent, ToolOutput
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.exceptions import (
    ModelAPIError,
    ModelConnectionError,
    ModelHTTPError,
    ModelTimeoutError,
    UnexpectedModelBehavior,
)
from pydantic_ai.models.bedrock import BedrockConverseModel
from pydantic_ai.providers.bedrock import BedrockProvider

from app.modules.utilities.domain.bedrock import TRANSIENT_ERROR_CODES
from app.modules.utilities.domain.provider_errors import BedrockInvocationError
from app.modules.utilities.domain.retry import retry_with_backoff

if TYPE_CHECKING:
    from mypy_boto3_bedrock_runtime import BedrockRuntimeClient

__all__ = ["bedrock_model", "run_bedrock_agent", "structured_agent"]

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3
_BASE_DELAY_SECONDS = 1.0


def bedrock_model(model_id: str, client: BedrockRuntimeClient) -> BedrockConverseModel:
    """A Converse model on the caller's own boto3 client, so its timeouts apply."""
    return BedrockConverseModel(model_id, provider=BedrockProvider(bedrock_client=client))


def structured_agent[T: BaseModel](
    schema: type[T], *, name: str, output_retries: int, instructions: str | None = None
) -> Agent[None, T]:
    """An agent whose only output is `schema`, called as tool `name`.

    No text output is allowed, so Bedrock is forced to call the tool
    (`toolChoice: any`). `output_retries` is how many times a schema or
    validator failure is sent back to the model before the run fails.
    """
    return Agent(
        name=name,
        output_type=ToolOutput(schema, name=name),
        instructions=instructions,
        retries={"output": output_retries},
    )


def _is_transient(exc: Exception) -> bool:
    # Pydantic AI wraps botocore transport failures as ModelConnectionError. A read
    # timeout already waited the client's full timeout (300s for meetings), so
    # retrying it would hold a summary slot for many minutes.
    if isinstance(exc, ModelConnectionError):
        return not isinstance(exc, ModelTimeoutError)
    return isinstance(exc, ModelHTTPError) and exc.provider_error_code in TRANSIENT_ERROR_CODES


def _error_code(exc: Exception) -> str:
    if isinstance(exc, ModelHTTPError):
        return exc.provider_error_code or str(exc.status_code)
    return type(exc).__name__


async def run_bedrock_agent[T](
    call: Callable[[], Awaitable[AgentRunResult[T]]],
    *,
    model_id: str,
    operation: str,
) -> T:
    """Run `call()` (one `agent.run(...)`) with transient-error retries and
    return its validated output. Raises `BedrockInvocationError` when the
    output never validates or AWS keeps failing.
    """

    def on_retry(attempt: int, exc: Exception, delay: float) -> None:
        logger.warning(
            "bedrock_invocation_failed operation=%s model_id=%s attempt=%d error_code=%s",
            operation,
            model_id,
            attempt,
            _error_code(exc),
            extra={
                "model_id": model_id,
                "operation": operation,
                "attempt": attempt,
                "error_code": _error_code(exc),
            },
        )

    started = time.monotonic()
    try:
        result = await retry_with_backoff(
            call,
            is_retryable=_is_transient,
            max_attempts=_MAX_ATTEMPTS,
            delay_seconds=lambda attempt: _BASE_DELAY_SECONDS * (2 ** (attempt - 1)),
            on_retry=on_retry,
        )
    except UnexpectedModelBehavior:
        # `from None`: the original carries the model's own output.
        raise BedrockInvocationError(f"{operation} output failed validation") from None
    except ModelAPIError as exc:
        raise BedrockInvocationError(f"{operation} failed: {_error_code(exc)}") from None

    latency_ms = int((time.monotonic() - started) * 1000)
    usage = result.usage
    logger.info(
        "bedrock_invocation_succeeded operation=%s model_id=%s latency_ms=%d "
        "input_tokens=%s output_tokens=%s requests=%s",
        operation,
        model_id,
        latency_ms,
        usage.input_tokens,
        usage.output_tokens,
        usage.requests,
        extra={
            "model_id": model_id,
            "operation": operation,
            "latency_ms": latency_ms,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "requests": usage.requests,
        },
    )
    return result.output
