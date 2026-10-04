"""The one Bedrock call this module makes — reading the advisor's free-text
note into a `ParsedContext`. The implementation owns its own
validate-repair-retry-then-fail-closed policy and returns a domain value —
never the Pydantic schema, which must not cross this Port.
"""

from typing import Protocol

from app.modules.discrepancies.domain.criteria import ParsedContext


class ContextExtractor(Protocol):
    async def extract(self, text: str) -> ParsedContext: ...
