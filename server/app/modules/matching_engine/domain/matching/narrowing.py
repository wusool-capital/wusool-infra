"""What the SQL candidate load may safely rule out before scoring — built only
from the buyer role's own CRM fields, never from LLM-extracted values, so the
narrowing is as trustworthy as a `human_confirmed` hard requirement.

Every field is optional and means "no restriction" when unset: a seller with
missing data is never dropped here, same pass-through rule as
`apply_structured_filters`.
"""

from dataclasses import dataclass

from app.modules.discovery.domain.geography import (
    TARGET_REGION_OPTIONS,
    country_spellings,
    resolve_known,
)
from app.modules.matching_engine.domain.buyers import BuyerContext
from app.modules.matching_engine.domain.matching.overrides import advisor_stated_values
from app.modules.matching_engine.domain.requirements import RequirementProfile
from app.modules.utilities.domain.money import Money

# `target_region` options that resolve to a country list — the rest (Africa,
# Europe, ...) can't be enumerated, so they disable geography. Aliases are
# spellings sellers' `region` is known to carry, so they aren't dropped as strangers.
_RESOLVABLE_REGIONS = ("GCC", "GCC-wide", "Gulf", "MENA", "Middle East", "MENATP")

_REGION_NAMES = frozenset(r.lower() for r in TARGET_REGION_OPTIONS)


def _is_region(value: str) -> bool:
    # An unresolvable region (Europe) is still a region, never a literal country to match.
    return resolve_known(value) is not None or value.strip().lower() in _REGION_NAMES


@dataclass(frozen=True)
class CandidateNarrowing:
    vertical: str | None = None
    # Lower-cased. Both empty means geography is not narrowed at all.
    regions: frozenset[str] = frozenset()
    countries: frozenset[str] = frozenset()
    ev_ceiling: float | None = None

    @property
    def narrows_geography(self) -> bool:
        return bool(self.regions or self.countries)

    @classmethod
    def from_buyer(
        cls, buyer: BuyerContext, profile: RequirementProfile | None = None
    ) -> "CandidateNarrowing":
        """Uses the buyer role's CRM fields, except a dimension the advisor
        restated in their own context — that value replaces the stored one."""
        stated = advisor_stated_values(profile) if profile else {}
        vertical = buyer.target_vertical
        target_regions, target_countries = buyer.target_region, buyer.target_country
        if "sector" in stated:
            vertical = stated["sector"][0]
        if "geography" in stated:
            target_regions = [v for v in stated["geography"] if _is_region(v)]
            target_countries = [v for v in stated["geography"] if not _is_region(v)]

        ev_ceiling = _amount(buyer.ev_ceiling)
        if profile and profile.advisor_limits.ev_ceiling is not None:
            ev_ceiling = profile.advisor_limits.ev_ceiling

        regions, countries = _accepted_geography(target_regions, target_countries)
        return cls(
            vertical=vertical.strip().lower() if vertical else None,
            regions=regions,
            countries=countries,
            ev_ceiling=ev_ceiling,
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

    for country in list(countries):
        countries |= country_spellings(country)

    return frozenset(regions), frozenset(countries)
