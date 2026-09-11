"""Real AWS Bedrock implementation of `ExtractionClient`, using the Converse
API. Mirrors `matching_engine.providers.bedrock.client.BedrockConverseClient`'s
validate -> repair-prompt retry -> fail-closed policy, narrowed to this
module's single extraction operation.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

from pydantic import ValidationError

from app.modules.enrichment.application.ports.llm import RepairPromptBuilder
from app.modules.enrichment.providers.bedrock.boto_client import get_bedrock_runtime_client
from app.modules.enrichment.providers.bedrock.schemas import ExtractedFields
from app.modules.utilities import BedrockInvocationError
from app.modules.utilities.domain.json_types import JsonObject

if TYPE_CHECKING:
    from mypy_boto3_bedrock_runtime.type_defs import ConverseResponseTypeDef

logger = logging.getLogger(__name__)


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
        raw = self._converse(model_id, prompt, temperature, max_tokens, output_schema)
        validated, error = self._validate(raw)

        if validated is None:
            raw_retry = self._converse(
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

    def _converse(
        self,
        model_id: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
        output_schema: JsonObject,
    ) -> JsonObject:
        response: ConverseResponseTypeDef = self._client.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"temperature": temperature, "maxTokens": max_tokens},
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
                "toolChoice": {"tool": {"name": "return_structured_output"}},
            },
        )
        return self._extract_json(response)

    @staticmethod
    def _extract_json(response: ConverseResponseTypeDef) -> JsonObject:
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
        return {}
