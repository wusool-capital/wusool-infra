"""The provider-agnostic seam application services depend on. `requirements`
and `matching` import this Protocol, never `boto3` or
`app.modules.matching_engine.providers.bedrock` directly — swapping
providers later means writing a new implementation of this Protocol, not
touching the application layer.

Each method owns its own validate-retry-then-fail-closed policy internally
(validating against its own vendor-response schema, in
`providers/bedrock/schemas.py`) and returns framework-free values — never
the Pydantic schema itself, which must not cross this Port. A failed check
is retried once with the error appended to the same conversation, so the
caller's prompt stays the whole business context; a second failure raises
`BedrockInvocationError`.
"""

from typing import Protocol

from app.modules.matching_engine.application.ports.llm_types import (
    ExtractedRequirements,
    InferenceConfig,
)
from app.modules.matching_engine.domain.matching.entities import ReasoningOutcome

__all__ = ["BedrockClient", "ExtractedRequirements", "InferenceConfig"]


class BedrockClient(Protocol):
    async def extract_requirements(
        self,
        *,
        model_id: str,
        prompt: str,
        inference_config: InferenceConfig,
    ) -> ExtractedRequirements: ...

    async def generate_reasoning(
        self,
        *,
        model_id: str,
        prompt: str,
        inference_config: InferenceConfig,
    ) -> ReasoningOutcome: ...
