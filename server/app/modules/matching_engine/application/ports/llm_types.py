"""Dataclasses referenced by `application/ports/llm.py`'s `BedrockClient`
Protocol — kept apart from the Protocol itself per convention."""

from dataclasses import dataclass


@dataclass(frozen=True)
class InferenceConfig:
    """Bedrock inference parameters — from `Settings`, never hardcoded."""

    temperature: float
    max_tokens: int
    top_p: float
