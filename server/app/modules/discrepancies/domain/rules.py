"""The two branches (§ conflicts stored criteria; required fields
null/thin), as pure functions. The advisor's note arrives already extracted
as a `ParsedContext`; rules decide and `template_message` writes the words.
"""

from app.modules.discovery.domain.geography import resolve_known
from app.modules.discrepancies.domain.criteria import (
    BuyerCriteria,
    Discrepancy,
    DiscrepancyReport,
    ParsedContext,
)
from app.modules.discrepancies.domain.vocabulary import (
    CRITERION_LABELS,
    Criterion,
    is_unrestricted_region,
)
from app.modules.enrichment.domain.missingness import is_missing


def _vertical_conflict(criteria: BuyerCriteria, stated: str | None) -> Discrepancy | None:
    if stated is None or criteria.target_vertical is None or stated == criteria.target_vertical:
        return None
    return Discrepancy(
        Criterion.VERTICAL, "conflict", stored=criteria.target_vertical, stated=stated
    )


def _region_conflict(criteria: BuyerCriteria, stated: str | None) -> Discrepancy | None:
    if (
        stated is None
        or not criteria.target_region
        or stated in criteria.target_region
        or is_unrestricted_region(stated)
    ):
        return None

    covered_countries: set[str] = set()
    for stored in criteria.target_region:
        if is_unrestricted_region(stored):
            return None
        scope = resolve_known(stored)
        if scope is None:
            # An unresolvable stored region (Africa, Asia, Europe, ...) —
            # can't rule out coverage, so stay silent rather than guess.
            return None
        if scope.unrestricted:
            return None
        covered_countries |= scope.countries

    stated_scope = resolve_known(stated)
    covered = (
        stated_scope is None
        or stated_scope.unrestricted
        or bool(stated_scope.countries & covered_countries)
    )
    if covered:
        return None

    return Discrepancy(
        Criterion.GEOGRAPHY, "conflict", stored=", ".join(criteria.target_region), stated=stated
    )


def _format_amount(value: float | None) -> str:
    return f"USD {value:,.0f}" if value is not None else "not set"


def _format_range(low: float | None, high: float | None) -> str:
    return f"{_format_amount(low)} - {_format_amount(high)}"


def _ticket_conflict(
    criteria: BuyerCriteria, low: float | None, high: float | None
) -> Discrepancy | None:
    if low is None or (criteria.check_size_min is None and criteria.check_size_max is None):
        return None
    stated_high = high if high is not None else low
    below = criteria.check_size_max is not None and low > criteria.check_size_max
    above = criteria.check_size_min is not None and stated_high < criteria.check_size_min
    if not (below or above):
        return None
    return Discrepancy(
        Criterion.TICKET_BAND,
        "conflict",
        stored=_format_range(criteria.check_size_min, criteria.check_size_max),
        stated=_format_range(low, stated_high),
    )


def _ebitda_conflict(criteria: BuyerCriteria, stated: float | None) -> Discrepancy | None:
    if stated is None or (criteria.ebitda_floor is None and criteria.ebitda_ceiling is None):
        return None
    below = criteria.ebitda_floor is not None and stated < criteria.ebitda_floor
    above = criteria.ebitda_ceiling is not None and stated > criteria.ebitda_ceiling
    if not (below or above):
        return None
    return Discrepancy(
        Criterion.EBITDA,
        "conflict",
        stored=_format_range(criteria.ebitda_floor, criteria.ebitda_ceiling),
        stated=_format_amount(stated),
    )


def find_conflicts(criteria: BuyerCriteria, context: ParsedContext) -> tuple[Discrepancy, ...]:
    conflicts = (
        _vertical_conflict(criteria, context.vertical),
        _region_conflict(criteria, context.region),
        _ticket_conflict(criteria, context.ticket_low, context.ticket_high),
        _ebitda_conflict(criteria, context.ebitda),
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
    if is_missing(criteria.ebitda_floor):
        missing.append(Discrepancy(Criterion.EBITDA, "missing", stored="(not set)"))
    return tuple(missing)


def run_checks(criteria: BuyerCriteria, context: ParsedContext) -> DiscrepancyReport:
    return DiscrepancyReport(
        buyer_role_id=criteria.buyer_role_id,
        conflicts=find_conflicts(criteria, context),
        missing=find_missing(criteria),
    )


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} and {items[-1]}"


def template_message(
    criteria: BuyerCriteria, report: DiscrepancyReport, *, context_checked: bool
) -> str:
    """Never says "no conflicting details" unless the note was actually checked."""
    org = criteria.org_name
    lines = [
        f"Heads up: {org}'s profile says {CRITERION_LABELS[d.criterion]} is {d.stored}, "
        f"but you said {d.stated}."
        for d in report.conflicts
    ]
    if report.missing:
        missing = _join([CRITERION_LABELS[d.criterion] for d in report.missing])
        lines.append(f"Heads up: {org}'s profile is missing {missing}.")
    if not context_checked:
        lines.append(
            "Your note couldn't be checked for conflicts."
            if report.missing
            else f"Nothing is missing from {org}'s profile, but your note couldn't be "
            "checked for conflicts."
        )
    elif report.is_clear:
        lines.append(f"No missing or conflicting details found for {org}.")
    return "\n".join(lines)
