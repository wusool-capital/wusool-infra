"""The two branches (§ conflicts stored criteria; required fields
null/thin), as pure functions — rules decide, the one Bedrock call in
`application/check.py` only phrases what these already found.
"""

import re

from app.modules.discovery.domain.geography import resolve_known
from app.modules.discrepancies.domain.criteria import BuyerCriteria, Discrepancy, DiscrepancyReport
from app.modules.discrepancies.domain.vocabulary import (
    REGION_OPTIONS,
    VERTICAL_OPTIONS,
    Criterion,
    is_unrestricted_region,
)
from app.modules.enrichment.domain.missingness import is_missing
from app.modules.utilities.domain.money import parse_usd_amount

# A bare number is never money on its own — only a `$`, a literal `USD`, or
# a magnitude suffix (K/M/B/thousand/million/billion) makes it one. A range
# can write the suffix once, shared ("$5-15M"), or on either/both bounds
# ("$5M-15M", "$5M to $15M") — each bound's own suffix wins when present,
# otherwise it borrows the other bound's, so "$5M-15" still reads as $15M.
_MONEY_RE = re.compile(
    r"(?P<usd>USD\s*)?(?P<dollar>\$)?\s*"
    r"(?P<low>[0-9][0-9,]*(?:\.[0-9]+)?)\s*(?P<low_suffix>k|m|b|thousand|million|billion)?"
    r"(?:\s*(?:-|to)\s*(?:USD\s*)?\$?\s*"
    r"(?P<high>[0-9][0-9,]*(?:\.[0-9]+)?)\s*(?P<high_suffix>k|m|b|thousand|million|billion)?)?"
    r"\b",
    re.IGNORECASE,
)
_SUFFIX_LETTER = {
    "k": "K",
    "thousand": "K",
    "m": "M",
    "million": "M",
    "b": "B",
    "billion": "B",
}
_EBITDA_KEYWORDS = ("ebitda",)
_TICKET_KEYWORDS = ("ticket", "check size", "check-size", "cheque size", "invest", "deal size")
_PROXIMITY_CHARS = 40


class ParsedContext:
    def __init__(
        self,
        *,
        vertical: str | None = None,
        region: str | None = None,
        ticket_low: float | None = None,
        ticket_high: float | None = None,
        ebitda: float | None = None,
    ) -> None:
        self.vertical = vertical
        self.region = region
        self.ticket_low = ticket_low
        self.ticket_high = ticket_high
        self.ebitda = ebitda


def _first_phrase_match(text: str, options: frozenset[str] | tuple[str, ...]) -> str | None:
    for option in sorted(options, key=len, reverse=True):
        if re.search(rf"\b{re.escape(option)}\b", text, re.IGNORECASE):
            return option
    return None


def _normalize_amount(number: str, suffix: str | None) -> float | None:
    letter = _SUFFIX_LETTER.get((suffix or "").lower(), "")
    try:
        return parse_usd_amount(f"USD {number.replace(',', '')}{letter}")
    except ValueError:
        return None


def parse_context(text: str) -> ParsedContext:
    """Deterministic, no Bedrock call — a vertical/region hit is a
    whole-word phrase match (longest option first, so "Southeast Asia"
    wins over "Asia"); a money mention only counts once an EBITDA or
    ticket-size keyword sits within `_PROXIMITY_CHARS` of it, so
    "$20M revenue" is never mistaken for a ticket-size conflict.
    """
    vertical = _first_phrase_match(text, VERTICAL_OPTIONS)
    region = _first_phrase_match(text, REGION_OPTIONS)

    ticket_low: float | None = None
    ticket_high: float | None = None
    ebitda: float | None = None

    for match in _MONEY_RE.finditer(text):
        low_suffix = match.group("low_suffix")
        high_suffix = match.group("high_suffix")
        if not (match.group("usd") or match.group("dollar") or low_suffix or high_suffix):
            continue
        low = _normalize_amount(match.group("low"), low_suffix or high_suffix)
        if low is None:
            continue
        high = (
            _normalize_amount(match.group("high"), high_suffix or low_suffix)
            if match.group("high")
            else None
        )

        window = text[max(0, match.start() - _PROXIMITY_CHARS) : match.end() + _PROXIMITY_CHARS]
        window_lower = window.lower()
        if ebitda is None and any(k in window_lower for k in _EBITDA_KEYWORDS):
            ebitda = low
        elif ticket_low is None and any(k in window_lower for k in _TICKET_KEYWORDS):
            ticket_low, ticket_high = low, (high if high is not None else low)

    return ParsedContext(
        vertical=vertical,
        region=region,
        ticket_low=ticket_low,
        ticket_high=ticket_high,
        ebitda=ebitda,
    )


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
        stored=f"{criteria.check_size_min} - {criteria.check_size_max}",
        stated=f"{low} - {stated_high}",
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
        stored=f"{criteria.ebitda_floor} - {criteria.ebitda_ceiling}",
        stated=str(stated),
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


def run_checks(criteria: BuyerCriteria, context_text: str | None) -> DiscrepancyReport:
    context = parse_context(context_text) if context_text else ParsedContext()
    return DiscrepancyReport(
        buyer_role_id=criteria.buyer_role_id,
        conflicts=find_conflicts(criteria, context),
        missing=find_missing(criteria),
    )


def template_message(criteria: BuyerCriteria, report: DiscrepancyReport) -> str:
    lines = [f"*Discrepancy check for {criteria.org_name}*"]
    if report.conflicts:
        lines.append("_Conflicts with what's on file:_")
        lines.extend(
            f"• {d.criterion.value}: on file `{d.stored}`, you said `{d.stated}`"
            for d in report.conflicts
        )
    if report.missing:
        lines.append("_Missing from the buyer's profile:_")
        lines.extend(f"• {d.criterion.value}" for d in report.missing)
    if report.is_clear:
        lines.append("No conflicts or missing criteria found.")
    return "\n".join(lines)
