"""Real AWS Bedrock implementation of `SummarizerLLM`, using the Converse
API. Retries transient errors only, via
`utilities.providers.bedrock.retry.invoke_bedrock_with_retry` — the same
shared wrapper `enrichment`'s and `lead_magnets`' clients use.

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

from typing import TYPE_CHECKING

from pydantic import ValidationError

from app.modules.meetings.providers.bedrock.boto_client import get_bedrock_runtime_client
from app.modules.meetings.providers.bedrock.schemas import MeetingSummarySchema
from app.modules.utilities.domain.bedrock import converse_kwargs
from app.modules.utilities.domain.json_types import JsonObject
from app.modules.utilities.domain.provider_errors import BedrockInvocationError
from app.modules.utilities.providers.bedrock.retry import invoke_bedrock_with_retry

if TYPE_CHECKING:
    # boto3-stubs is a dev-only type-checking dependency (see pyproject.toml)
    # — never installed in the production image, so this import must stay
    # inside TYPE_CHECKING (and `from __future__ import annotations` above
    # keeps the annotations below from being evaluated at runtime).
    from mypy_boto3_bedrock_runtime.type_defs import ConverseResponseTypeDef

_OPERATION = "summarization"


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

        def converse() -> ConverseResponseTypeDef:
            return self._converse(
                model_id, prompt, system_prompt, max_tokens, temperature, output_schema
            )

        raw = await invoke_bedrock_with_retry(
            converse=converse, model_id=model_id, operation=_OPERATION
        )
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
