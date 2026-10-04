"""Fake `ContextExtractor` — records the notes it was asked to read and
returns a scripted `ParsedContext`, or raises when given an exception.
"""

from app.modules.discrepancies.domain.criteria import ParsedContext


class FakeContextExtractor:
    def __init__(self, response: ParsedContext | Exception) -> None:
        self._response = response
        self.texts: list[str] = []

    async def extract(self, text: str) -> ParsedContext:
        self.texts.append(text)
        if isinstance(self._response, Exception):
            raise self._response
        return self._response
