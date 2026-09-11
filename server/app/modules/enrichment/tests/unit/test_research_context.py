"""`build_research_query`/`build_known_facts_block` — a bare org name alone
produces a generic, run-to-run-inconsistent Firecrawl search (confirmed live:
"Investcorp company profile" returned one thin LinkedIn snippet). These turn
whatever context we already have into a sharper query and a grounding block
for the extraction prompt.
"""

from app.modules.enrichment.domain.research_context import (
    CompanyContext,
    build_known_facts_block,
    build_research_query,
)


def test_query_falls_back_to_bare_name_when_nothing_else_is_known() -> None:
    context = CompanyContext(org_name="Investcorp")

    assert build_research_query(context) == "Investcorp company profile"


def test_query_anchors_on_domain_when_known() -> None:
    context = CompanyContext(
        org_name="Raoof Plus",
        domains=("raoofplus.com",),
        sector_focus=("Utilities",),
        hq_country="US",
    )

    query = build_research_query(context)

    assert query == "Raoof Plus raoofplus.com company profile"


def test_query_enriches_with_sector_and_country_when_no_domain() -> None:
    context = CompanyContext(
        org_name="Raoof Plus",
        sector_focus=("Utilities", "Cybersecurity"),
        hq_country="US",
    )

    query = build_research_query(context)

    assert query == "Raoof Plus Utilities Cybersecurity US company profile"


def test_query_uses_categories_when_sector_focus_is_empty() -> None:
    context = CompanyContext(org_name="Acme Co", categories=("SaaS",), hq_country="UAE")

    query = build_research_query(context)

    assert query == "Acme Co SaaS UAE company profile"


def test_query_is_capped_in_length() -> None:
    context = CompanyContext(
        org_name="A" * 100,
        domains=("b" * 100 + ".com",),
    )

    assert len(build_research_query(context)) <= 150


def test_known_facts_block_is_empty_when_nothing_is_known() -> None:
    context = CompanyContext(org_name="Investcorp")

    assert build_known_facts_block(context) == ""


def test_known_facts_block_includes_populated_fields_only() -> None:
    context = CompanyContext(
        org_name="Raoof Plus",
        domains=("raoofplus.com",),
        hq_country="US",
        sector_focus=("Utilities",),
    )

    block = build_known_facts_block(context)

    assert "Domain: raoofplus.com" in block
    assert "HQ country: US" in block
    assert "Sector: Utilities" in block
    assert "Category:" not in block
    assert "LinkedIn:" not in block
