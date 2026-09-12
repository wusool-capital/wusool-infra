"""Real AWS Bedrock implementation of `ExtractionClient`, using the Converse
API. Mirrors `matching_engine.providers.bedrock.client.BedrockConverseClient`'s
validate -> repair-prompt retry -> fail-closed policy, narrowed to this
module's single extraction operation.

The `converse` request shape, response parsing, and transient-error set are
shared with every other Bedrock caller via `utilities.domain.bedrock`, and
the entire retry-with-logging wrapper via
`utilities.providers.bedrock.retry.invoke_bedrock_with_retry` — same as
`lead_magnets`' own client (`matching_engine`'s still hand-rolls its own
loop, predating that helper's extraction; new callers should use the shared
one, not mirror the older pattern). This file owns only what's genuinely
its own: the repair-retry validation policy above the retry loop.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import ValidationError

from app.modules.enrichment.application.ports.llm import RepairPromptBuilder
from app.modules.enrichment.providers.bedrock.boto_client import get_bedrock_runtime_client
from app.modules.enrichment.providers.bedrock.schemas import ExtractedFields
from app.modules.utilities import BedrockInvocationError
from app.modules.utilities.domain.bedrock import converse_kwargs
from app.modules.utilities.domain.json_types import JsonObject
from app.modules.utilities.providers.bedrock.retry import invoke_bedrock_with_retry

if TYPE_CHECKING:
    from mypy_boto3_bedrock_runtime.type_defs import ConverseResponseTypeDef

_OPERATION = "enrichment_extraction"


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

        def converse() -> ConverseResponseTypeDef:
            return self._converse(model_id, prompt, temperature, max_tokens, output_schema)

        return await invoke_bedrock_with_retry(
            converse=converse, model_id=model_id, operation=_OPERATION
        )

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
