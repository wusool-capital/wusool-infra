"""A fake implementing `FirecrawlClient` for tests — no real Firecrawl calls."""

from app.modules.matching_engine.domain.web_search import WebSourcedLead


class FakeFirecrawlClient:
    """Returns a scripted list of leads regardless of query — set
    `leads` directly, or leave empty to simulate "no leads found".
    """

    def __init__(self, leads: list[WebSourcedLead] | None = None) -> None:
        self.leads = leads or []
        self.calls: list[tuple[str, str, int]] = []

    async def find_potential_sellers(
        self, *, industry: str, geography: str, limit: int
    ) -> list[WebSourcedLead]:
        self.calls.append((industry, geography, limit))
        return self.leads[:limit]
