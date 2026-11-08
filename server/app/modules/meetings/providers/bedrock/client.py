"""Real AWS Bedrock implementation of `SummarizerLLM` and `CorrectorLLM`,
built on Pydantic AI agents over the Converse API.

Each agent's `output_type` is a `ToolOutput` with no text output allowed,
so Bedrock is forced to call the output tool (`toolChoice: any`), and the
agent validates the result into the schema before we see it. A failed
schema check or a broken summary length rule (`summary_limit_issues`) gets
one retry with the error sent back to the model; after that a schema
failure raises and a length overshoot is accepted, since a slightly long
summary beats a failed meeting.

Transient AWS errors are retried here around the whole agent run, with the
same codes, backoff and per-attempt logging as
`utilities.providers.bedrock.retry` — botocore's own retry modes skip
`ModelTimeoutException`. The boto3 client keeps its 300s `read_timeout`
(see `boto_client.py`).

Logs metadata only: model id, operation, latency, token usage and request
count — never prompt or response content. Pydantic AI's errors can embed
model output, so they are replaced, not chained, when re-raised.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable

from botocore.exceptions import EndpointConnectionError
from pydantic_ai import Agent, ModelRetry, RunContext, ToolOutput
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError, UnexpectedModelBehavior
from pydantic_ai.models.bedrock import BedrockConverseModel, BedrockModelSettings
from pydantic_ai.providers.bedrock import BedrockProvider

from app.modules.meetings.domain.corrections import CorrectionSuggestion
from app.modules.meetings.domain.summary import MeetingSummary, summary_limit_issues
from app.modules.meetings.providers.bedrock.boto_client import get_bedrock_runtime_client
from app.modules.meetings.providers.bedrock.schemas import (
    MeetingSummarySchema,
    TranscriptCorrectionsSchema,
)
from app.modules.utilities.domain.bedrock import TRANSIENT_ERROR_CODES
from app.modules.utilities.domain.provider_errors import BedrockInvocationError
from app.modules.utilities.domain.retry import retry_with_backoff

logger = logging.getLogger(__name__)

_OPERATION = "summarization"
_CORRECTION_OPERATION = "transcript_correction"
_MAX_ATTEMPTS = 3
_BASE_DELAY_SECONDS = 1.0
# One repair round, matching the old validate-repair-retry policy.
_OUTPUT_RETRIES = 1


def _check_limits(ctx: RunContext[bool], output: MeetingSummarySchema) -> MeetingSummarySchema:
    if not ctx.deps or ctx.retry >= ctx.max_retries:
        return output
    issues = summary_limit_issues(output.to_domain())
    if issues:
        raise ModelRetry(" ".join(issues))
    return output


def _is_transient(exc: Exception) -> bool:
    if isinstance(exc, EndpointConnectionError):
        return True
    return isinstance(exc, ModelHTTPError) and exc.provider_error_code in TRANSIENT_ERROR_CODES


def _error_code(exc: Exception) -> str:
    if isinstance(exc, ModelHTTPError):
        return exc.provider_error_code or str(exc.status_code)
    return type(exc).__name__


class BedrockConverseClient:
    def __init__(self) -> None:
        self._provider = BedrockProvider(bedrock_client=get_bedrock_runtime_client())
        # deps is check_limits: map-step excerpts are dense on purpose, so only final
        # summaries are held to the length rules.
        self.summary_agent: Agent[bool, MeetingSummarySchema] = Agent(
            name="meeting_summary",
            deps_type=bool,
            output_type=ToolOutput(MeetingSummarySchema, name="meeting_summary"),
            retries={"output": _OUTPUT_RETRIES},
        )
        self.summary_agent.output_validator(_check_limits)
        self.corrections_agent: Agent[None, TranscriptCorrectionsSchema] = Agent(
            name="transcript_corrections",
            output_type=ToolOutput(TranscriptCorrectionsSchema, name="transcript_corrections"),
            retries={"output": _OUTPUT_RETRIES},
        )

    async def summarize(
        self,
        *,
        model_id: str,
        prompt: str,
        system_prompt: str,
        max_tokens: int,
        temperature: float,
        check_limits: bool,
    ) -> MeetingSummary:
        settings = BedrockModelSettings(max_tokens=max_tokens, temperature=temperature)
        model = self._model(model_id)
        result = await self._run(
            lambda: self.summary_agent.run(
                prompt,
                model=model,
                instructions=system_prompt,
                model_settings=settings,
                deps=check_limits,
            ),
            model_id=model_id,
            operation=_OPERATION,
        )
        return result.output.to_domain()

    async def suggest_corrections(
        self,
        *,
        model_id: str,
        prompt: str,
        system_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> list[CorrectionSuggestion]:
        settings = BedrockModelSettings(max_tokens=max_tokens, temperature=temperature)
        model = self._model(model_id)
        result = await self._run(
            lambda: self.corrections_agent.run(
                prompt, model=model, instructions=system_prompt, model_settings=settings
            ),
            model_id=model_id,
            operation=_CORRECTION_OPERATION,
        )
        return result.output.to_domain()

    def _model(self, model_id: str) -> BedrockConverseModel:
        return BedrockConverseModel(model_id, provider=self._provider)

    async def _run[T](
        self,
        call: Callable[[], Awaitable[AgentRunResult[T]]],
        *,
        model_id: str,
        operation: str,
    ) -> AgentRunResult[T]:
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
            # `from None`: the original carries the model's (transcript-derived) output.
            raise BedrockInvocationError(f"{operation} output failed validation") from None
        except (ModelAPIError, EndpointConnectionError) as exc:
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
        return result
