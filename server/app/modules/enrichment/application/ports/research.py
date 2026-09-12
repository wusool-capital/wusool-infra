"""The provider-agnostic seam `EnrichMixin` depends on for gathering public
source material. Never imports `firecrawl` directly here — swapping
providers later means writing a new implementation of this Protocol, not
touching the application layer.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SourceDocument:
    url: str
    title: str
    content: str


class ResearchClient(Protocol):
    async def search(self, query: str, *, limit: int) -> list[SourceDocument]: ...
