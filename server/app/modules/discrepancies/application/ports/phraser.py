"""The one Bedrock call this module makes — turning a flagged
`DiscrepancyReport` into a sentence. Mirrors `enrichment.application.ports
.llm.ExtractionClient`: the implementation owns its own
validate-repair-retry-then-fail-closed policy internally and returns a
plain, already-validated `dict` — never the Pydantic schema itself, which
must not cross this Port.
"""

from collections.abc import Callable
from typing import Protocol

from app.modules.utilities.domain.json_types import JsonObject

RepairPromptBuilder = Callable[[JsonObject, str], str]


class DiscrepancyPhraser(Protocol):
    async def phrase_report(
        self,
        *,
        model_id: str,
        prompt: str,
        repair_prompt_builder: RepairPromptBuilder,
        temperature: float,
        max_tokens: int,
    ) -> JsonObject: ...
