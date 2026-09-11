"""The provider-agnostic seam `EnrichMixin` depends on for turning source
material into field proposals. Each implementation owns its own
validate-repair-retry-then-fail-closed policy internally and returns a
plain, already-validated `dict` — never the Pydantic schema itself, which
must not cross this Port. Mirrors `matching_engine.application.ports.llm`.
"""

from collections.abc import Callable
from typing import Protocol

from app.modules.utilities.domain.json_types import JsonObject

RepairPromptBuilder = Callable[[JsonObject, str], str]


class ExtractionClient(Protocol):
    async def extract_fields(
        self,
        *,
        model_id: str,
        prompt: str,
        repair_prompt_builder: RepairPromptBuilder,
        temperature: float,
        max_tokens: int,
    ) -> JsonObject: ...
