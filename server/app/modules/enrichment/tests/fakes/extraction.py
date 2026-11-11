"""Fake `ExtractionClient` for tests — returns a canned response instead of
calling Bedrock.
"""

from collections.abc import Callable

from app.modules.enrichment.application.ports.llm import ExtractionClient
from app.modules.enrichment.domain.proposals import ExtractedField

type ExtractionResponse = tuple[ExtractedField, ...]


class FakeExtractionClient(ExtractionClient):
    def __init__(
        self, response: ExtractionResponse | Callable[[], ExtractionResponse] = ()
    ) -> None:
        self._response = response
        self.prompts: list[str] = []

    async def extract_fields(
        self,
        *,
        model_id: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> ExtractionResponse:
        self.prompts.append(prompt)
        return self._response() if callable(self._response) else self._response
