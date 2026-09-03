"""The provider-agnostic seam application services depend on. `requirements`
and `matching` import this Protocol, never `boto3` or
`app.modules.matching_engine.providers.bedrock` directly — swapping
providers later means writing a new implementation of this Protocol, not
touching the application layer.

Each method owns its own validate-repair-retry-then-fail-closed policy
internally (validating against its own vendor-response schema, in
`providers/bedrock/schemas.py`) and returns a plain, already-validated
`dict` — never the Pydantic schema itself, which must not cross this Port.
`repair_prompt_builder` is a callback (given the invalid raw response and
the validation error) so the *content* of a repair prompt — which needs
the original business context (buyer, profile, shortlist) — stays owned by
the caller, while the *retry loop itself* (attempt count, when to call it,
when to fail closed) is owned here, one layer down.
"""

from collections.abc import Callable
from typing import Protocol

from app.modules.matching_engine.application.ports.llm_types import InferenceConfig
from app.modules.utilities.domain.json_types import JsonObject

RepairPromptBuilder = Callable[[JsonObject, str], str]


class BedrockClient(Protocol):
    async def extract_requirements(
        self,
        *,
        model_id: str,
        prompt: str,
        repair_prompt_builder: RepairPromptBuilder,
        inference_config: InferenceConfig,
    ) -> JsonObject: ...

    async def generate_reasoning(
        self,
        *,
        model_id: str,
        prompt: str,
        repair_prompt_builder: RepairPromptBuilder,
        inference_config: InferenceConfig,
    ) -> JsonObject: ...
