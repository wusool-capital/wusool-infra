"""Tool sector value -> `organizations.sector_focus` option title.

Each tool asks for a sector in its own vocabulary, and none of them matches
the CRM's. Writing a raw tool value to Attio fails the select-option lookup,
and the live relay only logs that — so the sector silently goes missing.

Two rules make that impossible here:

1. Every target is checked against the live option set at import
   (`ddl_commands/api/organizations.py`'s `sector_focus`, 85 options), so a
   typo or a renamed option is a startup failure rather than a failed write.
2. An unmapped input **raises**. It does not fall back to
   "Diversified / Generalist" — a wrong sector is worse than a missing one,
   because it silently misfiles the lead and skews any sector report built
   on it.

The benchmark mappings below are the full set for that tool's 31 dropdown
values, with the compound "Supply Chain or mobility" split so mobility keeps
its own target. The valuation tool's own vocabulary is 225 labels and is
**not** mapped here — see `UNMAPPED_VOCABULARIES`.
"""

from app.modules.lead_magnets.domain.sector_options import SECTOR_FOCUS_OPTIONS

# The GCC SME Benchmark's established-business dropdown (20 values).
_BENCHMARK_SME = {
    "aesthetics": "Beauty & Personal Care",
    "agency": "Marketing / AdTech",
    "auto": "Garage",
    "cleaning": "Consumer & Lifestyle Services",
    "contracting": "Construction & Engineering",
    "ecommerce": "Retail / E-Commerce",
    "fitness": "Sports & Wellness",
    "grocery": "Retail / E-Commerce",
    "itservices": "IT Services / Distribution",
    "laundry": "Consumer & Lifestyle Services",
    "logistics": "Logistics / 3PL / Freight",
    "manufacturing": "Industrial Manufacturing",
    "medical": "Healthcare Services / Clinics",
    "nursery": "Nursery",
    "realestate": "Residential / Commercial Real Estate",
    "restaurant": "Food & Beverage / QSR",
    "salon": "Beauty & Personal Care",
    "trading": "Supply Chain / Distribution",
    "training": "EdTech / Education",
    "travel": "Hospitality / Hotels / Tourism",
}

# The benchmark's tech/startup dropdown. "Supply Chain or mobility" is split
# so a mobility business is not filed as distribution: both targets are live
# options, so nothing needed creating in Attio.
_BENCHMARK_TECH = {
    "AI": "AI / ML",
    "SaaS": "SaaS / Cloud",
    "Fintech": "Fintech",
    "Digital Health": "Healthtech / Digital Health",
    "Supply Chain": "Supply Chain / Distribution",
    "Mobility": "Mobility",
    "FoodTech": "Food Manufacturing / FoodTech",
    "E-commerce": "Retail / E-Commerce",
    "Proptech": "Property Management / Proptech",
    "Edtech": "EdTech / Education",
    # Still the pre-split label. Kept so a submission from the current form,
    # before the option is split, does not raise. Remove once the form ships
    # the two separate options.
    "Supply Chain or mobility": "Supply Chain / Distribution",
    # The other compound flagged for review; unlike mobility this one has
    # not been decided, so it keeps the source's own target.
    "DeepTech or hardware": "Space / Deep Tech",
    "Other": "Diversified / Generalist",
}

BENCHMARK_SECTORS: dict[str, str] = {**_BENCHMARK_SME, **_BENCHMARK_TECH}

# Vocabularies that deliberately have no mapping yet. Naming them here means
# `to_sector_focus` raises with a useful message rather than a bare KeyError,
# and the gap is visible in code rather than only in a document.
UNMAPPED_VOCABULARIES = (
    "the valuation tool's ALL_SECTORS (225 labels, chosen by /enrich)",
    "the M&A Readiness form's own sector dropdown",
)


class UnmappedSectorError(ValueError):
    """Raised rather than defaulting. A wrong sector silently misfiles the
    lead and skews any sector report built on it, which is worse than a
    missing one."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"no sector_focus mapping for {value!r}. Add it to "
            f"domain/sector_mapping.py rather than defaulting — still unmapped: "
            f"{'; '.join(UNMAPPED_VOCABULARIES)}"
        )
        self.value = value


def to_sector_focus(value: str | None) -> str | None:
    """The `sector_focus` option title for a tool's own sector value.

    `None` in, `None` out — an unanswered optional field is not an error.
    Anything else must map, or this raises.
    """
    if value is None or not value.strip():
        return None

    raw = value.strip()
    if raw in BENCHMARK_SECTORS:
        return BENCHMARK_SECTORS[raw]

    # A value that is already an option title passes through: `/enrich` picks
    # from a list that overlaps the CRM's, and the readiness form may too.
    if raw in SECTOR_FOCUS_OPTIONS:
        return raw

    lowered = raw.lower()
    for source, target in BENCHMARK_SECTORS.items():
        if source.lower() == lowered:
            return target
    for option in SECTOR_FOCUS_OPTIONS:
        if option.lower() == lowered:
            return option

    raise UnmappedSectorError(raw)


def _assert_targets_are_live() -> None:
    """Every target must be a real option, checked at import.

    Attio rejects an undefined select value, and the live relay only logs
    that — so a typo here would silently drop the sector on every write. A
    startup failure is the cheaper outcome.
    """
    unknown = sorted({t for t in BENCHMARK_SECTORS.values() if t not in SECTOR_FOCUS_OPTIONS})
    if unknown:
        raise RuntimeError(f"sector_mapping targets are not live sector_focus options: {unknown}")


_assert_targets_are_live()
