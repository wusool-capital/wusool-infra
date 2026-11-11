"""A fake implementing `BedrockClient` for unit/e2e tests — no AWS calls.

Mirrors `BedrockConverseClient`'s validate-retry-then-fail-closed policy
(re-validating against the same `providers/bedrock/schemas.py` schemas and
monetary check) so tests exercising that policy (one retry, fail closed
after two failures) see the same externally-observable behavior a real
Bedrock-backed client would, without any AWS call.
"""

from pydantic import ValidationError

from app.modules.matching_engine.application.ports.llm import (
    ExtractedRequirements,
    InferenceConfig,
)
from app.modules.matching_engine.domain.matching.entities import ReasoningOutcome
from app.modules.matching_engine.providers.bedrock.schemas import (
    ExtractedRequirementProfile,
    ReasoningResult,
)
from app.modules.utilities.domain.provider_errors import BedrockInvocationError


class FakeBedrockClient:
    """Returns a scripted sequence of raw responses per operation, one per
    underlying model call (so a retry consumes a second entry from the same
    list). Set `structured_responses`/`reasoning_responses` to a list; each
    call pops the next one. A response of `"__raise__"` raises instead (for
    testing permanent-failure paths in the calling service).

    `structured_calls`/`reasoning_calls` record what the model was sent per
    call: the prompt first, then the validation error on a retry, as the
    real agent appends it to the conversation.
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

    @staticmethod
    def _next_raw(responses: list[dict], calls: list[str], sent: str, operation: str) -> dict:
        calls.append(sent)
        if not responses:
            raise AssertionError(f"FakeBedrockClient.{operation} called with no responses left")
        response = responses.pop(0)
        if response == "__raise__":
            raise RuntimeError("simulated permanent Bedrock failure")
        return response

    async def extract_requirements(
        self,
        *,
        model_id: str,
        prompt: str,
        inference_config: InferenceConfig,
    ) -> ExtractedRequirements:
        sent = prompt
        for _ in range(2):
            raw = self._next_raw(
                self.structured_responses, self.structured_calls, sent, "extract_requirements"
            )
            try:
                extracted = ExtractedRequirementProfile.model_validate(raw)
            except ValidationError as exc:
                sent = str(exc)
                continue
            issue = extracted.monetary_issue()
            if issue is None:
                return extracted.to_domain()
            sent = issue
        raise BedrockInvocationError("extraction output failed validation")

    async def generate_reasoning(
        self,
        *,
        model_id: str,
        prompt: str,
        inference_config: InferenceConfig,
    ) -> ReasoningOutcome:
        sent = prompt
        for _ in range(2):
            raw = self._next_raw(
                self.reasoning_responses, self.reasoning_calls, sent, "generate_reasoning"
            )
            try:
                return ReasoningResult.model_validate(raw).to_domain()
            except ValidationError as exc:
                sent = str(exc)
        raise BedrockInvocationError("reasoning output failed validation")
