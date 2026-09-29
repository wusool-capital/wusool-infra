"""Fake `DiscrepancyPhraser` — records prompts, returns a scripted response
or raises when the caller sets it to `"__raise__"`. Mirrors
`enrichment.tests.fakes.extraction.FakeExtractionClient`.
"""

from collections.abc import Callable

from app.modules.discrepancies.application.ports.phraser import RepairPromptBuilder
from app.modules.utilities.domain.json_types import JsonObject


class FakePhraser:
    def __init__(self, response: JsonObject | str | Callable[[], JsonObject | str]) -> None:
        self._response = response
        self.prompts: list[str] = []

    async def phrase_report(
        self,
        *,
        model_id: str,
        prompt: str,
        repair_prompt_builder: RepairPromptBuilder,
        temperature: float,
        max_tokens: int,
    ) -> JsonObject:
        self.prompts.append(prompt)
        response = self._response() if callable(self._response) else self._response
        if response == "__raise__":
            raise RuntimeError("phrasing failed")
        return response
