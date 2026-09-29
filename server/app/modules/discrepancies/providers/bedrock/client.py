"""Real AWS Bedrock implementation of `DiscrepancyPhraser`, using the
Converse API. Mirrors `enrichment.providers.bedrock.client
.BedrockConverseClient`'s validate -> repair-prompt retry -> fail-closed
policy, narrowed to this module's single phrasing operation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import ValidationError

from app.modules.discrepancies.application.ports.phraser import RepairPromptBuilder
from app.modules.discrepancies.providers.bedrock.boto_client import get_bedrock_runtime_client
from app.modules.discrepancies.providers.bedrock.schemas import PhrasedMessage
from app.modules.utilities import BedrockInvocationError
from app.modules.utilities.domain.bedrock import converse_kwargs
from app.modules.utilities.domain.json_types import JsonObject
from app.modules.utilities.providers.bedrock.retry import invoke_bedrock_with_retry

if TYPE_CHECKING:
    from mypy_boto3_bedrock_runtime.type_defs import ConverseResponseTypeDef

_OPERATION = "discrepancy_phrasing"


class BedrockConverseClient:
    def __init__(self) -> None:
        self._client = get_bedrock_runtime_client()

    async def phrase_report(
        self,
        *,
        model_id: str,
        prompt: str,
        repair_prompt_builder: RepairPromptBuilder,
        temperature: float,
        max_tokens: int,
    ) -> JsonObject:
        output_schema = PhrasedMessage.model_json_schema()
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
                f"discrepancy phrasing failed validation after one repair attempt: {error}"
            )
        return validated

    @staticmethod
    def _validate(raw: JsonObject) -> tuple[JsonObject | None, str | None]:
        try:
            return PhrasedMessage.model_validate(raw).model_dump(), None
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
