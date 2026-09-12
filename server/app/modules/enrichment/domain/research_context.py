"""What we already know about a target company, and how to turn that into
a better free-text research query than a bare `"{org_name} company profile"`
— see `application.enrich._research_and_extract`, the only caller.
"""

from dataclasses import dataclass

_QUERY_SUFFIX = "company profile"
_MAX_ENRICHMENT_TOKENS = 2
_MAX_QUERY_LENGTH = 150


@dataclass(frozen=True)
class CompanyContext:
    org_name: str
    domains: tuple[str, ...] = ()
    sector_focus: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    hq_country: str | None = None
    geographic_focus: tuple[str, ...] = ()
    description: str | None = None
    linkedin: str | None = None


def build_research_query(context: CompanyContext) -> str:
    """Anchor on the company's own domain when we have one — the strongest
    possible disambiguator against a same-named company. Otherwise enrich
    the bare name with sector/category and HQ country tokens. Falls back to
    today's exact query when nothing else is known.
    """
    if context.domains:
        query = f"{context.org_name} {context.domains[0]} {_QUERY_SUFFIX}"
        return query[:_MAX_QUERY_LENGTH]

    tokens = [*context.sector_focus, *context.categories][:_MAX_ENRICHMENT_TOKENS]
    if context.hq_country:
        tokens.append(context.hq_country)

    if not tokens:
        return f"{context.org_name} {_QUERY_SUFFIX}"

    query = f"{context.org_name} {' '.join(tokens)} {_QUERY_SUFFIX}"
    return query[:_MAX_QUERY_LENGTH]


def build_known_facts_block(context: CompanyContext) -> str:
    """Rendered into the extraction prompt so the LLM can reject source
    material about a different, same-named company. Empty when nothing
    beyond the bare name is known.
    """
    facts: list[str] = []
    if context.domains:
        facts.append(f"Domain: {context.domains[0]}")
    if context.hq_country:
        facts.append(f"HQ country: {context.hq_country}")
    if context.sector_focus:
        facts.append(f"Sector: {', '.join(context.sector_focus)}")
    if context.categories:
        facts.append(f"Category: {', '.join(context.categories)}")
    if context.geographic_focus:
        facts.append(f"Geographic focus: {', '.join(context.geographic_focus)}")
    if context.linkedin:
        facts.append(f"LinkedIn: {context.linkedin}")
    if context.description:
        facts.append(f"Description: {context.description}")

    if not facts:
        return ""

    fact_lines = "\n".join(f"- {fact}" for fact in facts)
    return (
        "What we already know about this company (use it to verify source "
        f"material below is actually about THIS company, not a same-named "
        f"one):\n{fact_lines}\n"
    )
