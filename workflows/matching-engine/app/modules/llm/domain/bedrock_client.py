"""The provider-agnostic seam application services depend on. `requirements`
and `matching` import this Protocol, never `boto3` or `app.integrations.bedrock`
directly — swapping providers later means writing a new implementation of
this Protocol, not touching the application layer.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class InferenceConfig:
    """Bedrock inference parameters — from `Settings`, never hardcoded."""

    temperature: float
    max_tokens: int
    top_p: float


class BedrockClient(Protocol):
    async def generate_structured(
        self, *, model_id: str, prompt: str, inference_config: InferenceConfig
    ) -> dict: ...

    async def generate_reasoning(
        self, *, model_id: str, prompt: str, inference_config: InferenceConfig
    ) -> dict: ...
