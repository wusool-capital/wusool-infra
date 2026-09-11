"""Real AWS Bedrock implementation of `ExtractionClient`, using the Converse
API. Mirrors `matching_engine.providers.bedrock.client.BedrockConverseClient`'s
validate -> repair-prompt retry -> fail-closed policy, narrowed to this
module's single extraction operation.

The `converse` request shape, response parsing, and transient-error set are
shared with every other Bedrock caller via `utilities.domain.bedrock` — this
file owns only what's genuinely its own: the repair-retry validation policy,
and the bounded transient-error retry loop (`_invoke`), same split
`matching_engine`'s own client documents.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from botocore.exceptions import ClientError, EndpointConnectionError
from pydantic import ValidationError

from app.modules.enrichment.application.ports.llm import RepairPromptBuilder
from app.modules.enrichment.providers.bedrock.boto_client import get_bedrock_runtime_client
from app.modules.enrichment.providers.bedrock.schemas import ExtractedFields
from app.modules.utilities import BedrockInvocationError
from app.modules.utilities.domain.bedrock import (
    TRANSIENT_ERROR_CODES,
    converse_kwargs,
    extract_json,
)
from app.modules.utilities.domain.json_types import JsonObject

if TYPE_CHECKING:
    from mypy_boto3_bedrock_runtime.type_defs import ConverseResponseTypeDef

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3
_BASE_DELAY_SECONDS = 1.0


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
        which retries on a *schema* failure with a different prompt. Runs
        the blocking boto3 call via `asyncio.to_thread`, same as every
        other Bedrock caller in this codebase — a raw synchronous call here
        would block the event loop for the duration of every enrichment
        request.
        """
        last_error: Exception | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                response = await asyncio.to_thread(
                    self._converse, model_id, prompt, temperature, max_tokens, output_schema
                )
                return extract_json(response)
            except ClientError as exc:
                last_error = exc
                error_code = exc.response.get("Error", {}).get("Code", "")
                logger.warning(
                    "enrichment_bedrock_invocation_failed model_id=%s attempt=%d error_code=%s",
                    model_id,
                    attempt,
                    error_code,
                )
                if error_code not in TRANSIENT_ERROR_CODES or attempt == _MAX_ATTEMPTS:
                    raise BedrockInvocationError(
                        f"enrichment extraction failed: {error_code}"
                    ) from exc
                await asyncio.sleep(_BASE_DELAY_SECONDS * (2 ** (attempt - 1)))
            except EndpointConnectionError as exc:
                last_error = exc
                if attempt == _MAX_ATTEMPTS:
                    raise BedrockInvocationError(
                        "enrichment extraction failed: connection error"
                    ) from exc
                await asyncio.sleep(_BASE_DELAY_SECONDS * (2 ** (attempt - 1)))
        raise BedrockInvocationError(
            f"enrichment extraction failed after {_MAX_ATTEMPTS} attempts"
        ) from last_error

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
