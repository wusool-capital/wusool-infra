"""A fake implementing `BedrockClient` for unit/e2e tests — no AWS calls.

Mirrors `BedrockConverseClient`'s own validate-repair-retry-then-fail-closed
policy (re-validating against the same `providers/bedrock/schemas.py`
schemas) so tests exercising that policy (one repair retry, fail closed
after two failures) see the same externally-observable behavior a real
Bedrock-backed client would, without any AWS call.
"""

from pydantic import ValidationError

from app.modules.matching_engine.application.ports.llm import InferenceConfig, RepairPromptBuilder
from app.modules.matching_engine.domain.matching.scoring import is_monetary_criterion
from app.modules.matching_engine.providers.bedrock.schemas import (
    ExtractedRequirementProfile,
    ReasoningResult,
)
from app.modules.utilities.domain.money import parse_usd_amount
from app.modules.utilities.domain.provider_errors import BedrockInvocationError


class FakeBedrockClient:
    """Returns a scripted sequence of raw responses per operation, one per
    underlying model call (so a repair retry consumes a second entry from
    the same list). Set `structured_responses`/`reasoning_responses` to a
    list; each call pops the next one. A response of `"__raise__"` raises
    instead (for testing permanent-failure paths in the calling service).
    """

    def __init__(
        self,
        structured_responses: list[dict] | None = None,
        reasoning_responses: list[dict] | None = None,
    ) -> None:
        self.structured_responses = list(structured_responses or [])
        self.reasoning_responses = list(reasoning_responses or [])
        self.structured_calls: list[str] = []
        self.reasoning_calls: list[str] = []

    async def _next_structured_raw(self, prompt: str) -> dict:
        self.structured_calls.append(prompt)
        if not self.structured_responses:
            raise AssertionError(
                "FakeBedrockClient.extract_requirements called with no responses left"
            )
        response = self.structured_responses.pop(0)
        if response == "__raise__":
            raise RuntimeError("simulated permanent Bedrock failure")
        return response

    async def extract_requirements(
        self,
        *,
        model_id: str,
        prompt: str,
        repair_prompt_builder: RepairPromptBuilder,
        inference_config: InferenceConfig,
    ) -> dict:
        raw = await self._next_structured_raw(prompt)
        validated, error = self._validate_extraction(raw)
        if validated is None:
            raw_retry = await self._next_structured_raw(repair_prompt_builder(raw, error or ""))
            validated, error = self._validate_extraction(raw_retry)
        if validated is None:
            raise BedrockInvocationError(
                f"extraction output failed validation after one repair attempt: {error}"
            )
        return validated

    @staticmethod
    def _validate_extraction(raw: dict) -> tuple[dict | None, str | None]:
        try:
            extracted = ExtractedRequirementProfile.model_validate(raw)
            for requirement in [*extracted.hard_requirements, *extracted.soft_preferences]:
                if is_monetary_criterion(requirement.criterion) and requirement.value is not None:
                    parse_usd_amount(requirement.value)
            return extracted.model_dump(), None
        except (ValidationError, ValueError) as exc:
            return None, str(exc)

    async def _next_reasoning_raw(self, prompt: str) -> dict:
        self.reasoning_calls.append(prompt)
        if not self.reasoning_responses:
            raise AssertionError(
                "FakeBedrockClient.generate_reasoning called with no responses left"
            )
        response = self.reasoning_responses.pop(0)
        if response == "__raise__":
            raise RuntimeError("simulated permanent Bedrock failure")
        return response

    async def generate_reasoning(
        self,
        *,
        model_id: str,
        prompt: str,
        repair_prompt_builder: RepairPromptBuilder,
        inference_config: InferenceConfig,
    ) -> dict:
        raw = await self._next_reasoning_raw(prompt)
        validated, error = self._validate_reasoning(raw)
        if validated is None:
            raw_retry = await self._next_reasoning_raw(repair_prompt_builder(raw, error or ""))
            validated, error = self._validate_reasoning(raw_retry)
        if validated is None:
            raise BedrockInvocationError(
                f"reasoning output failed validation after one repair attempt: {error}"
            )
        return validated

    @staticmethod
    def _validate_reasoning(raw: dict) -> tuple[dict | None, str | None]:
        try:
            return ReasoningResult.model_validate(raw).model_dump(), None
        except ValidationError as exc:
            return None, str(exc)
