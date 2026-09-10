"""The valuation tool's three AI helpers and their prompts.

The prompts are checked for the constraints that were learned the hard way
rather than chosen, because losing one of them is silent: the output still
parses, it is just wrong.
"""

import pytest

from app.modules.lead_magnets.application.valuation.valuation_ai import ValuationAi
from app.modules.lead_magnets.domain.shared.prompts import (
    analyze_prompt,
    compare_query_prompt,
    compare_select_prompt,
    enrich_prompt,
)
from app.modules.lead_magnets.domain.shared.search import SearchResult


class _FakeLlm:
    def __init__(self, *, analyze_raises: bool = False, **responses) -> None:
        self.responses = responses
        self.prompts: dict[str, str] = {}
        self.analyze_raises = analyze_raises

    def _record(self, name: str, prompt: str):
        self.prompts[name] = prompt
        return self.responses.get(name, {})

    async def enrich(self, *, prompt):
        return self._record("enrich", prompt)

    async def analyze(self, *, prompt):
        if self.analyze_raises:
            raise RuntimeError("bedrock down")
        return self._record("analyze", prompt)

    async def plan_search_queries(self, *, prompt):
        return self._record("plan", prompt)

    async def select_comparables(self, *, prompt):
        return self._record("select", prompt)

    async def score_readiness(self, *, prompt):
        return self._record("score", prompt)

    async def advise_readiness(self, *, prompt):
        return self._record("advise", prompt)

    async def qualify_buyer(self, *, prompt):
        return self._record("qualify", prompt)


class _FakeSearch:
    def __init__(self, *, page: str = "", results=None, raises=False) -> None:
        self.page = page
        self.results = results or []
        self.raises = raises
        self.queries: list[str] = []
        self.scraped: list[str] = []

    async def search(self, query, *, limit):
        self.queries.append(query)
        if self.raises:
            raise RuntimeError("firecrawl down")
        return list(self.results)

    async def scrape(self, url):
        self.scraped.append(url)
        return self.page


def test_enrich_prompt_has_no_web_search_instruction() -> None:
    """Bedrock cannot search for Claude, so the live prompt's "use web search
    to find the company's website" would be an instruction the model cannot
    follow. The page is passed in instead."""
    prompt = enrich_prompt(
        company="Acme", domain="acme.ae", page_text="We fit out offices.", sector_list=["AI"]
    )
    assert "web search" not in prompt.lower()
    assert "WEBSITE CONTENT" in prompt
    assert "We fit out offices." in prompt
    # The load-bearing instruction survives.
    assert "do NOT rely on the dictionary" in prompt


def test_enrich_prompt_says_what_to_do_with_a_missing_page() -> None:
    """Otherwise the model falls back to guessing from the domain name, which
    is exactly the failure the original warns about."""
    prompt = enrich_prompt(company="Acme", domain="acme.ae", page_text="", sector_list=["AI"])
    assert "could not be fetched" in prompt
    assert "rather than guessing" in prompt


def test_enrich_prompt_truncates_a_long_page() -> None:
    prompt = enrich_prompt(
        company="Acme", domain="acme.ae", page_text="x" * 50_000, sector_list=["AI"]
    )
    assert len(prompt) < 12_000


def test_query_prompt_forbids_naming_companies() -> None:
    """The constraint that matters most here. Asked for candidates too, the
    cheap model returned a property developer and an insurance company as
    comparables for an interior fit-out business, with invented tickers.
    """
    prompt = compare_query_prompt(
        company="Acme Fit-Out", sector="Construction", description="Offices"
    )
    assert "queries ONLY" in prompt
    assert "Do not name any company, ticker or figure" in prompt
    assert '"queries"' in prompt


def test_select_prompt_forbids_padding_and_invention() -> None:
    """Accuracy and quantity trade off: the honest answer is fewer
    comparables, and the shortfall is filled from static data instead."""
    prompt = compare_select_prompt(
        company="Acme",
        sector="Construction",
        description="Offices",
        revenue=3_000_000,
        search_results=[("T", "https://u", "S")],
    )
    assert "ONLY companies and figures that appear in the results" in prompt
    assert "Do NOT pad the list" in prompt
    assert "do NOT invent" in prompt
    assert "return an empty list" in prompt
    assert "[1] T" in prompt


def test_select_prompt_handles_no_results() -> None:
    prompt = compare_select_prompt(
        company="Acme", sector="X", description="", revenue=0, search_results=[]
    )
    assert "(no results were returned)" in prompt


def test_analyze_prompt_keeps_the_sector_override_authority() -> None:
    """The whole reason this call exists: automated classifiers mislabel
    businesses, and the analyst is allowed to overrule the tag."""
    prompt = analyze_prompt(
        company="Acme",
        domain="acme.ae",
        sector="EdTech",
        description="A plant nursery",
        geography="UAE",
        revenue=3_000_000,
        ebitda=460_000,
        sector_list=["EdTech", "Retail"],
    )
    assert "may be WRONG" in prompt
    assert "sector_fit" in prompt
    assert "closest_existing_sector" in prompt
    # Figures are formatted with separators, as the source does.
    assert "$3,000,000" in prompt
    assert "$460,000" in prompt


def test_analyze_prompt_bans_invented_metrics() -> None:
    """The scorecard must reference only the figures it was given."""
    prompt = analyze_prompt(
        company="Acme",
        domain="",
        sector="",
        description="",
        geography="",
        revenue=0,
        ebitda=0,
        sector_list=["AI"],
    )
    assert "Do not invent growth or retention metrics" in prompt
    assert "score 50 and say what is missing" in prompt


def test_analyze_prompt_no_longer_asks_for_comparables() -> None:
    """Comparables moved to `/compare`, because on Bedrock they need the
    Firecrawl pipeline and that is a different shape of call. Leaving the
    step in would pay for comps twice and produce two disagreeing sets."""
    prompt = analyze_prompt(
        company="Acme",
        domain="",
        sector="",
        description="",
        geography="",
        revenue=0,
        ebitda=0,
        sector_list=["AI"],
    )
    assert "Public comparables" not in prompt
    assert '"comps"' not in prompt


async def test_enrich_scrapes_the_given_domain_once() -> None:
    llm = _FakeLlm(enrich={"description": "d", "sector": "AI"})
    search = _FakeSearch(page="We fit out offices.")
    result = await ValuationAi(llm, search).enrich(domain="acme.ae")

    assert search.scraped == ["https://acme.ae"]
    assert search.queries == [], "enrich searches for nothing; the URL is already known"
    assert result == {"description": "d", "sector": "AI"}


async def test_enrich_keeps_an_existing_scheme() -> None:
    search = _FakeSearch()
    await ValuationAi(_FakeLlm(), search).enrich(domain="https://acme.ae/about")
    assert search.scraped == ["https://acme.ae/about"]


async def test_compare_fills_the_shortfall_from_static_data() -> None:
    """With search returning nothing, the table is filled from the sector set
    and the response says so."""
    llm = _FakeLlm(plan={"queries": ["gcc listed fit-out peers"]}, select={"comps": []})
    result = await ValuationAi(llm, _FakeSearch(results=[])).compare(
        company="Acme", sector="AI", description="", revenue=3_000_000
    )

    assert result["sourced"] == 0
    assert result["filled_from_static"] == len(result["comps"])
    assert result["comps"], "a known sector must still produce a table"


async def test_compare_reports_how_much_was_actually_sourced() -> None:
    llm = _FakeLlm(
        plan={"queries": ["q"]},
        select={"comps": [{"co": "Real Co", "tk": "REAL", "ev": 1, "rev": 1, "ebitda": 1}]},
    )
    search = _FakeSearch(results=[SearchResult(title="t", url="u", snippet="s")])
    result = await ValuationAi(llm, search).compare(
        company="Acme", sector="AI", description="", revenue=3_000_000
    )

    assert result["sourced"] == 1
    assert result["comps"][0]["tk"] == "REAL"
    assert result["filled_from_static"] == len(result["comps"]) - 1


async def test_compare_does_not_duplicate_a_sourced_ticker() -> None:
    """A static entry for a company search already found would appear twice
    in the table."""
    from app.modules.lead_magnets.domain.valuation.valuation import trading_comps_for_sector

    existing = trading_comps_for_sector("AI")[0]
    llm = _FakeLlm(
        plan={"queries": ["q"]},
        select={"comps": [{"co": existing.co, "tk": existing.tk, "ev": 1, "rev": 1, "ebitda": 1}]},
    )
    search = _FakeSearch(results=[SearchResult(title="t", url="u", snippet="s")])
    result = await ValuationAi(llm, search).compare(
        company="Acme", sector="AI", description="", revenue=1
    )

    tickers = [c["tk"] for c in result["comps"]]
    assert len(tickers) == len(set(tickers))


async def test_compare_survives_a_search_outage() -> None:
    """Firecrawl failing must degrade to the static set, not error — the
    visitor still gets a comparables table."""
    llm = _FakeLlm(plan={"queries": ["q1", "q2"]}, select={"comps": []})
    result = await ValuationAi(llm, _FakeSearch(raises=True)).compare(
        company="Acme", sector="AI", description="", revenue=1
    )
    assert result["comps"]
    assert result["sourced"] == 0


async def test_compare_skips_selection_when_no_queries_come_back() -> None:
    llm = _FakeLlm(plan={"queries": []}, select={"comps": [{"co": "X", "tk": "X"}]})
    result = await ValuationAi(llm, _FakeSearch()).compare(
        company="Acme", sector="AI", description="", revenue=1
    )
    assert "select" not in llm.prompts, "nothing to select from"
    assert result["sourced"] == 0


@pytest.mark.parametrize(
    "domain,expected",
    [("acme.ae", "acme"), ("www.acme-group.co", "acme group"), ("https://a_b.io/x", "a b")],
)
async def test_company_name_is_derived_from_the_domain_when_absent(domain, expected) -> None:
    llm = _FakeLlm()
    await ValuationAi(llm, _FakeSearch()).enrich(domain=domain)
    assert expected in llm.prompts["enrich"]


async def test_a_valuation_run_falls_back_without_any_model_call() -> None:
    """B9: the deterministic valuation must be reachable from the sweeper.

    `value_company` was verified over 3,000 cases but nothing dispatched it,
    so a valuation run whose AI failed resumed to `fallback -> None` and was
    finished as failed. The visitor is supposed to still get a real
    valuation — the model only picks the comparables that set the trading
    multiples.
    """
    from app.modules.lead_magnets.application.shared.pipelines import Pipelines

    pipelines = Pipelines(llm=None)  # type: ignore[arg-type]
    result = pipelines.fallback(
        "valuation",
        {
            "revenue": 3_000_000,
            "profit_before_tax": 400_000,
            "owner_salary": 60_000,
            "sector": "AI",
            "geography": "United Arab Emirates",
        },
    )

    assert result is not None
    assert result["mid"] > 0
    # Every method still contributes with the model gone.
    assert len(result["methods"]) == 5
    assert set(result["entry_values"]) == {
        "valuation_low",
        "valuation_mid",
        "valuation_high",
    }


def test_readiness_still_has_no_fallback() -> None:
    """The one tool that must not have one: its score, band and
    recommendations come only from the model."""
    from app.modules.lead_magnets.application.shared.pipelines import Pipelines

    assert Pipelines(llm=None).fallback("readiness", {}) is None  # type: ignore[arg-type]


async def test_a_valuation_resume_applies_stored_ai_output() -> None:
    """Comparables and discounts from `/compare` and `/analyze` are used when
    the payload carries them, so a resume produces the same figures as the
    original request rather than silently reverting to sector defaults."""
    from app.modules.lead_magnets.application.shared.pipelines import Pipelines

    pipelines = Pipelines(llm=None)  # type: ignore[arg-type]
    base = {
        "revenue": 3_000_000,
        "profit_before_tax": 400_000,
        "owner_salary": 60_000,
        "sector": "AI",
        "geography": "United Arab Emirates",
    }
    without = pipelines.fallback("valuation", base)
    with_ai = pipelines.fallback(
        "valuation",
        {
            **base,
            "comps": [{"co": "Tight Co", "tk": "TGT", "ev": 100, "rev": 50, "ebitda": 10}],
            "discounts": {"revenue_discount_pct": 20, "ebitda_discount_pct": 20},
        },
    )

    assert without is not None and with_ai is not None
    assert with_ai["mid"] != without["mid"]


async def test_analyze_falls_back_to_the_deterministic_pros_cons_insights_on_bedrock_failure() -> (
    None
):
    """A Bedrock failure must not surface as a bare error, the same way a
    benchmark/valuation AI failure never does."""
    valuation_ai = ValuationAi(_FakeLlm(analyze_raises=True), _FakeSearch())

    result = await valuation_ai.analyze(
        company="Acme",
        domain="acme.com",
        sector="",
        description="",
        geography="",
        revenue=1000,
        ebitda=-100,
    )

    assert set(result.keys()) == {"pros", "cons", "insights"}
    assert len(result["pros"]) == 3
    assert len(result["cons"]) == 3
    assert len(result["insights"]) == 2
    assert result["insights"][0]["title"] == (
        "Path to profitability is the highest-priority near-term milestone"
    )


async def test_analyze_success_never_touches_the_fallback() -> None:
    valuation_ai = ValuationAi(_FakeLlm(analyze={"sector_fit": "good"}), _FakeSearch())
    result = await valuation_ai.analyze(
        company="Acme",
        domain="acme.com",
        sector="",
        description="",
        geography="",
        revenue=0,
        ebitda=0,
    )
    assert result == {"sector_fit": "good"}
