"""What the SQL candidate load may safely rule out before scoring — built only
from the buyer role's own CRM fields, never from LLM-extracted values, so the
narrowing is as trustworthy as a `human_confirmed` hard requirement.

Every field is optional and means "no restriction" when unset: a seller with
missing data is never dropped here, same pass-through rule as
`apply_structured_filters`.
"""

from dataclasses import dataclass

from app.modules.discovery.domain.geography import resolve_known
from app.modules.matching_engine.domain.buyers import BuyerContext
from app.modules.utilities.domain.money import Money

# The only two `target_region` options that resolve to a country list — the
# rest (Africa, Europe, ...) can't be enumerated, so they disable geography.
_RESOLVABLE_REGIONS = ("GCC", "MENA")


@dataclass(frozen=True)
class CandidateNarrowing:
    vertical: str | None = None
    # Lower-cased. Both empty means geography is not narrowed at all.
    regions: frozenset[str] = frozenset()
    countries: frozenset[str] = frozenset()
    ticket_min: float | None = None
    ticket_max: float | None = None
    ev_ceiling: float | None = None

    @property
    def narrows_geography(self) -> bool:
        return bool(self.regions or self.countries)

    @classmethod
    def from_buyer(cls, buyer: BuyerContext) -> "CandidateNarrowing":
        regions, countries = _accepted_geography(buyer.target_region, buyer.target_country)
        return cls(
            vertical=buyer.target_vertical.strip().lower() if buyer.target_vertical else None,
            regions=regions,
            countries=countries,
            ticket_min=_amount(buyer.check_size_min),
            ticket_max=_amount(buyer.check_size_max),
            ev_ceiling=_amount(buyer.ev_ceiling),
        )


def _amount(money: Money | None) -> float | None:
    return money.amount if money is not None else None


def _accepted_geography(
    target_regions: list[str], target_countries: list[str]
) -> tuple[frozenset[str], frozenset[str]]:
    if not target_regions and not target_countries:
        return frozenset(), frozenset()

    countries = {c.strip().lower() for c in target_countries if c.strip()}
    regions = {r.strip().lower() for r in target_regions if r.strip()}

    for region in target_regions:
        scope = resolve_known(region)
        # An unresolvable or unrestricted region can't rule anyone out, so
        # the whole geography narrowing is dropped rather than guessed at.
        if scope is None or scope.unrestricted:
            return frozenset(), frozenset()
        countries |= {c.lower() for c in scope.countries}

    # A seller's own `region` (e.g. "GCC") can cover a wanted country without
    # naming it, so overlapping known regions are accepted too.
    for name in _RESOLVABLE_REGIONS:
        scope = resolve_known(name)
        if scope is not None and {c.lower() for c in scope.countries} & countries:
            regions.add(name.lower())

    return frozenset(regions), frozenset(countries)
