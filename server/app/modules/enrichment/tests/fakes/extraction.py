"""Fake `ExtractionClient` for tests — returns a canned response instead of
calling Bedrock.
"""

from collections.abc import Callable

from app.modules.enrichment.application.ports.llm import ExtractionClient, RepairPromptBuilder
from app.modules.utilities.domain.json_types import JsonObject


class FakeExtractionClient(ExtractionClient):
    def __init__(self, response: JsonObject | Callable[[], JsonObject]) -> None:
        self._response = response
        self.prompts: list[str] = []

    async def extract_fields(
        self,
        *,
        model_id: str,
        prompt: str,
        repair_prompt_builder: RepairPromptBuilder,
        temperature: float,
        max_tokens: int,
    ) -> JsonObject:
        self.prompts.append(prompt)
        return self._response() if callable(self._response) else self._response
