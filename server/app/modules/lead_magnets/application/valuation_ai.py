"""The valuation tool's three AI helpers: enrich, analyze and compare.

Stateless. None of them writes to the ledger, because none of them is a
submission — they build the report the visitor reads while still in the
tool. The valuation submission itself goes through the write contract like
every other tool.

`compare` is the one piece Bedrock cannot do natively: search is not
available for Claude at all, so the live tool's `web_search` is replaced by
a three-step pipeline — a cheap model plans the queries, Firecrawl runs
them, and the main model selects comparables from the results. Any shortfall
is filled from the static sector set rather than by letting a model invent
figures.
"""

import asyncio
import logging

from app.modules.lead_magnets.application.ports import LeadLLMPort, SearchPort
from app.modules.lead_magnets.domain.prompts import (
    analyze_prompt,
    compare_query_prompt,
    compare_select_prompt,
    enrich_prompt,
)
from app.modules.lead_magnets.domain.valuation import trading_comps_for_sector
from app.modules.lead_magnets.domain.valuation_data import sectors
from app.modules.utilities.domain.json_types import JsonObject

logger = logging.getLogger(__name__)

# The live prompt asks for 6 to 8 listed peers.
_TARGET_COMPS = 8
_RESULTS_PER_QUERY = 5


class ValuationAi:
    def __init__(self, llm: LeadLLMPort, search: SearchPort) -> None:
        self._llm = llm
        self._search = search

    async def enrich(self, *, domain: str, company: str | None = None) -> JsonObject:
        """Description and sector from the company's own page.

        One scrape of the URL the visitor gave us, not a search: the site is
        already known, so there was never anything to search for.
        """
        url = domain if domain.startswith("http") else f"https://{domain}"
        page = await self._search.scrape(url)
        if not page:
            logger.warning("lead_magnet_enrich_page_empty domain=%s", domain)

        return await self._llm.enrich(
            prompt=enrich_prompt(
                company=company or _company_from_domain(domain),
                domain=domain,
                page_text=page,
                sector_list=list(sectors()),
            )
        )

    async def analyze(
        self,
        *,
        company: str,
        domain: str,
        sector: str,
        description: str,
        geography: str,
        revenue: float,
        ebitda: float,
        website_text: str = "",
    ) -> JsonObject:
        return await self._llm.analyze(
            prompt=analyze_prompt(
                company=company,
                domain=domain,
                sector=sector,
                description=description,
                geography=geography,
                revenue=revenue,
                ebitda=ebitda,
                sector_list=list(sectors()),
                website_text=website_text,
            )
        )

    async def compare(
        self,
        *,
        company: str,
        sector: str,
        description: str,
        revenue: float,
        geography: str = "",
    ) -> JsonObject:
        """Comparables, grounded in search results.

        Returns `{"comps": [...], "sourced": n, "filled_from_static": n}` so
        the caller can be honest about how much of the table was researched
        versus filled from sector data.
        """
        planned = await self._llm.plan_search_queries(
            prompt=compare_query_prompt(
                company=company, sector=sector, description=description, geography=geography
            )
        )
        queries = [q for q in planned.get("queries", []) if isinstance(q, str) and q.strip()]

        results: list[tuple[str, str, str]] = []
        if queries:
            batches = await asyncio.gather(
                *(self._search.search(q, limit=_RESULTS_PER_QUERY) for q in queries),
                return_exceptions=True,
            )
            for batch in batches:
                if isinstance(batch, BaseException):
                    logger.warning("lead_magnet_compare_search_failed error=%s", batch)
                    continue
                results.extend((r.title, r.url, r.snippet) for r in batch)

        selected: list[JsonObject] = []
        if results:
            chosen = await self._llm.select_comparables(
                prompt=compare_select_prompt(
                    company=company,
                    sector=sector,
                    description=description,
                    revenue=revenue,
                    search_results=results,
                )
            )
            selected = [c for c in chosen.get("comps", []) if isinstance(c, dict)]
        else:
            logger.warning("lead_magnet_compare_no_search_results sector=%s", sector)

        sourced = len(selected)
        # Accuracy and quantity trade off: a model held to figures that
        # actually appear in the results returns fewer peers. The gap is
        # filled from the static sector set, never by inventing figures.
        if sourced < _TARGET_COMPS:
            have = {str(c.get("tk", "")).upper() for c in selected}
            for comp in trading_comps_for_sector(sector):
                if len(selected) >= _TARGET_COMPS:
                    break
                if comp.tk.upper() in have:
                    continue
                selected.append(
                    {
                        "co": comp.co,
                        "tk": comp.tk,
                        "ev": comp.ev,
                        "rev": comp.rev,
                        "ebitda": comp.ebitda,
                    }
                )

        return {
            "comps": selected,
            "sourced": sourced,
            "filled_from_static": len(selected) - sourced,
        }


def _company_from_domain(domain: str) -> str:
    host = domain.replace("https://", "").replace("http://", "").split("/")[0]
    return host.removeprefix("www.").rsplit(".", 1)[0].replace("-", " ").replace("_", " ")
