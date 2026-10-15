"""The two branches (§ conflicts stored criteria; required fields
null/thin), as pure functions. The advisor's note arrives already extracted
as a `ParsedContext`; rules decide and `template_message` writes the words.
"""

import re
from collections.abc import Iterable
from dataclasses import replace

from app.modules.discovery.domain.geography import country_spellings, resolve_known
from app.modules.discrepancies.domain.criteria import (
    BuyerCriteria,
    Discrepancy,
    DiscrepancyReport,
    ParsedContext,
)
from app.modules.discrepancies.domain.vocabulary import (
    CRITERION_FIELD_LABELS,
    GENERALIST_VERTICAL,
    REGION_OPTIONS,
    Criterion,
    regions_disjoint,
)
from app.modules.enrichment.domain.missingness import is_missing
from app.modules.notifications.domain.text import sanitize_mrkdwn

# Wider than `matching_engine`'s list; bare "check" (the verb) and "deal" are too loose.
_TICKET_WORDS = re.compile(
    r"\b(tickets?|che(?:que|ck)(?:[\s-]sizes?|s)|invest\w*|deal[\s-]sizes?)\b", re.IGNORECASE
)
_EBITDA_WORDS = re.compile(r"\bebitda\b", re.IGNORECASE)
# The same words `matching_engine` trusts for an EV cap, so the echo only shows
# what the match will actually apply.
_EV_WORDS = re.compile(r"\b(ev|enterprise value|valuation|valued)\b", re.IGNORECASE)
_REVENUE_WORDS = re.compile(r"\b(revenues?|turnover|sales)\b", re.IGNORECASE)


def _vertical_conflict(criteria: BuyerCriteria, candidates: tuple[str, ...]) -> Discrepancy | None:
    stored = criteria.target_vertical
    if (
        not candidates
        or stored in (None, GENERALIST_VERTICAL)
        or stored in candidates
        or GENERALIST_VERTICAL in candidates
    ):
        return None
    return Discrepancy(Criterion.VERTICAL, "conflict", stored=stored, stated=candidates[0])


def _spellings(countries: Iterable[str]) -> set[str]:
    return {s for c in countries for s in country_spellings(c)}


def _country_outside(country: str, criteria: BuyerCriteria) -> bool:
    """True only when the country is provably outside every stored region and
    country. An unresolvable stored region (Europe) is ruled out via a disjoint
    region the country sits in."""
    spellings = country_spellings(country)
    if spellings & _spellings(criteria.target_country):
        return False
    home = [
        r
        for r in REGION_OPTIONS
        if (scope := resolve_known(r)) is not None and spellings & _spellings(scope.countries)
    ]
    for region in criteria.target_region:
        scope = resolve_known(region)
        if scope is not None and scope.unrestricted:
            return False
        if scope is not None:
            if spellings & _spellings(scope.countries):
                return False
        elif not any(regions_disjoint(h, region) for h in home):
            return False
    return True


def _region_outside(region: str, criteria: BuyerCriteria) -> bool:
    if not all(regions_disjoint(region, stored) for stored in criteria.target_region):
        return False
    if not criteria.target_country:
        return True
    scope = resolve_known(region)
    if scope is None or scope.unrestricted:
        return False
    return not (_spellings(criteria.target_country) & _spellings(scope.countries))


def _geography_conflict(criteria: BuyerCriteria, context: ParsedContext) -> Discrepancy | None:
    """Conflict only when every stated place falls outside the buyer's regions and
    countries combined; anything that can't be resolved stays silent."""
    stated = ([context.region] if context.region else []) + list(context.countries)
    if not stated or not (criteria.target_region or criteria.target_country):
        return None
    outside = [_country_outside(c, criteria) for c in context.countries]
    if context.region:
        outside.append(_region_outside(context.region, criteria))
    if not all(outside):
        return None
    return Discrepancy(
        Criterion.GEOGRAPHY,
        "conflict",
        stored=", ".join([*criteria.target_region, *criteria.target_country]),
        stated=", ".join(stated),
    )


def _format_bounds(low: float | None, high: float | None) -> str:
    if low is not None and high is not None:
        return f"USD {low:,.0f}" if low == high else f"USD {low:,.0f} - USD {high:,.0f}"
    if low is not None:
        return f"at least USD {low:,.0f}"
    return f"up to USD {high:,.0f}" if high is not None else "not set"


def _band_conflict(
    criterion: Criterion,
    stored: tuple[float | None, float | None],
    stated: tuple[float | None, float | None],
) -> Discrepancy | None:
    """Conflict only when the stated range can't overlap the stored band —
    an open bound ("at least $2M") is never treated as an exact amount."""
    stored_low, stored_high = stored
    stated_low, stated_high = stated
    entirely_above = stated_low is not None and stored_high is not None and stated_low > stored_high
    entirely_below = stated_high is not None and stored_low is not None and stated_high < stored_low
    if not (entirely_above or entirely_below):
        return None
    return Discrepancy(
        criterion,
        "conflict",
        stored=_format_bounds(stored_low, stored_high),
        stated=_format_bounds(stated_low, stated_high),
    )


def ground(context: ParsedContext, note: str) -> ParsedContext:
    """Hybrid guard: keep an extracted amount only if the advisor's own words
    name what it measures. Only ever removes what the LLM found, never adds."""
    names_ticket = _TICKET_WORDS.search(note) is not None
    names_ebitda = _EBITDA_WORDS.search(note) is not None
    names_ev = _EV_WORDS.search(note) is not None
    names_revenue = _REVENUE_WORDS.search(note) is not None
    return replace(
        context,
        ticket_low=context.ticket_low if names_ticket else None,
        ticket_high=context.ticket_high if names_ticket else None,
        ebitda_low=context.ebitda_low if names_ebitda else None,
        ebitda_high=context.ebitda_high if names_ebitda else None,
        ev_ceiling=context.ev_ceiling if names_ev else None,
        revenue_low=context.revenue_low if names_revenue else None,
        revenue_high=context.revenue_high if names_revenue else None,
    )


def find_conflicts(criteria: BuyerCriteria, context: ParsedContext) -> tuple[Discrepancy, ...]:
    conflicts = (
        _vertical_conflict(criteria, context.verticals),
        _geography_conflict(criteria, context),
        _band_conflict(
            Criterion.TICKET_BAND,
            (criteria.check_size_min, criteria.check_size_max),
            (context.ticket_low, context.ticket_high),
        ),
        _band_conflict(
            Criterion.EBITDA,
            (criteria.ebitda_floor, criteria.ebitda_ceiling),
            (context.ebitda_low, context.ebitda_high),
        ),
    )
    return tuple(c for c in conflicts if c is not None)


def find_missing(criteria: BuyerCriteria) -> tuple[Discrepancy, ...]:
    missing = []
    if is_missing(criteria.target_vertical):
        missing.append(Discrepancy(Criterion.VERTICAL, "missing", stored="(not set)"))
    if is_missing(criteria.target_region) and is_missing(criteria.target_country):
        missing.append(Discrepancy(Criterion.GEOGRAPHY, "missing", stored="(not set)"))
    if is_missing(criteria.check_size_min) and is_missing(criteria.check_size_max):
        missing.append(Discrepancy(Criterion.TICKET_BAND, "missing", stored="(not set)"))
    if is_missing(criteria.ebitda_floor) and is_missing(criteria.ebitda_ceiling):
        missing.append(Discrepancy(Criterion.EBITDA, "missing", stored="(not set)"))
    return tuple(missing)


def run_checks(criteria: BuyerCriteria, context: ParsedContext) -> DiscrepancyReport:
    return DiscrepancyReport(
        buyer_role_id=criteria.buyer_role_id,
        conflicts=find_conflicts(criteria, context),
        missing=find_missing(criteria),
    )


def _fields(d: Discrepancy) -> str:
    return " / ".join(CRITERION_FIELD_LABELS[d.criterion])


def _context_lines(context: ParsedContext) -> list[str]:
    """One labelled line per thing read. A list, not a joined sentence: sector
    names contain slashes, which would blur where one ends and the next begins."""
    lines = []
    if context.verticals:
        label = "Sector (any of)" if len(context.verticals) > 1 else "Sector"
        lines.append(f"{label}: {', '.join(context.verticals)}")
    if context.region:
        lines.append(f"Region: {context.region}")
    if context.countries:
        label = "Countries" if len(context.countries) > 1 else "Country"
        lines.append(f"{label}: {', '.join(context.countries)}")
    if context.ticket_low is not None or context.ticket_high is not None:
        lines.append(f"Ticket: {_format_bounds(context.ticket_low, context.ticket_high)}")
    if context.ebitda_low is not None or context.ebitda_high is not None:
        lines.append(f"EBITDA: {_format_bounds(context.ebitda_low, context.ebitda_high)}")
    if context.ev_ceiling is not None:
        lines.append(f"EV ceiling: {_format_bounds(None, context.ev_ceiling)}")
    if context.revenue_low is not None or context.revenue_high is not None:
        lines.append(f"Revenue: {_format_bounds(context.revenue_low, context.revenue_high)}")
    if context.excluded_verticals:
        lines.append(f"Excluding: {', '.join(context.excluded_verticals)}")
    if context.seller_status:
        lines.append(f"Seller status: {', '.join(context.seller_status)}")
    if context.modifier_verticals:
        lines.append(f"Ranks higher (not required): {', '.join(context.modifier_verticals)}")
    return lines


def template_message(
    criteria: BuyerCriteria,
    report: DiscrepancyReport,
    *,
    context_checked: bool,
    context: ParsedContext | None = None,
) -> str:
    """Never says "no conflicting details" unless the note was actually checked.
    Echoes what was read from the note so a misread is visible."""
    org = sanitize_mrkdwn(criteria.org_name)
    lines = []
    if report.conflicts:
        lines.append(
            f"*{org}'s profile doesn't match your note*\n"
            + "\n".join(
                f"• {_fields(d)}: profile has {sanitize_mrkdwn(d.stored)}, "
                f"you said {sanitize_mrkdwn(d.stated or '')}"
                for d in report.conflicts
            )
        )
    if report.missing:
        lines.append(
            f"*Missing from {org}'s profile*\n"
            + "\n".join(f"• {_fields(d)}" for d in report.missing)
        )
    if not context_checked:
        lines.append(
            "Your note couldn't be checked for conflicts."
            if report.missing
            else f"Nothing is missing from {org}'s profile, but your note couldn't be "
            "checked for conflicts."
        )
    elif report.is_clear:
        lines.append(f"No missing or conflicting details found for {org}.")
    if context_checked and context is not None and not context.is_empty:
        read = "\n".join(f"• _{sanitize_mrkdwn(line)}_" for line in _context_lines(context))
        lines.append(f"_From your note:_\n{read}")
    return "\n\n".join(lines)
