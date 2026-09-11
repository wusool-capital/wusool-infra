"""Fake `ResearchClient` for tests — no network calls."""

from app.modules.enrichment.application.ports.research import ResearchClient, SourceDocument


class FakeResearchClient(ResearchClient):
    def __init__(self, documents: list[SourceDocument] | None = None) -> None:
        self.documents = documents or []
        self.queries: list[str] = []

    async def search(self, query: str, *, limit: int) -> list[SourceDocument]:
        self.queries.append(query)
        return self.documents[:limit]
