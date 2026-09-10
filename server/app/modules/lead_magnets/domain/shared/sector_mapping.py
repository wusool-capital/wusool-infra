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
its own target. The readiness mappings are the full set for that tool's own
11-value dropdown (`dopamine-readiness-score.html`'s `#cSector`, confirmed
live 2026-09-10 — a real `<select>`, not free text; a curl test against a
throwaway DB raised `UnmappedSectorError` on 10 of its 11 real options
before this table existed).

The valuation mappings are the full set for that tool's own 225-label
vocabulary (`ALL_SECTORS` in `dopamine-valuation.html`, also a `<select>`
— `/enrich` picks one when researching the company, and `/analyze` sees
the same list for its own reasoning; both were already correctly ported
before this table existed, since neither needs a CRM-side target). 21 of
the 225 already resolved via exact string match or by reusing the
benchmark table; `VALUATION_SECTORS` below covers the other 204.

These are fine-grained VC/startup labels against a coarser 85-option CRM
taxonomy, so several targets are real judgment calls rather than obvious
1:1 matches — flagged in `_VALUATION_SECTORS_FOR_REVIEW` below rather than
one comment per line, since with 204 entries most are unambiguous
("Automakers" -> "Automotive") and flagging every one would bury the ones
that actually need a second look.
"""

from app.modules.lead_magnets.domain.shared.sector_options import SECTOR_FOCUS_OPTIONS

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

# The M&A Readiness form's own dropdown (11 values, `#cSector`).
READINESS_SECTORS: dict[str, str] = {
    "Technology & SaaS": "SaaS / Cloud",
    "Healthcare & Medical": "Healthcare Services / Clinics",
    # Compound, like benchmark's "DeepTech or hardware": F&B is the more
    # common submission for a generalist SME assessment tool, so it is the
    # default target, not a settled decision. Flagged for the same review.
    "F&B & Hospitality": "Food & Beverage / QSR",
    "Professional Services": "Consulting / Advisory",
    "Education & Training": "EdTech / Education",
    "Retail & E-Commerce": "Retail / E-Commerce",
    "Construction & Contracting": "Construction & Engineering",
    "Logistics & Supply Chain": "Logistics / 3PL / Freight",
    "Financial Services": "Financial Services",
    "Manufacturing & Industrial": "Industrial Manufacturing",
    "Other": "Diversified / Generalist",
}

# The valuation tool's own 204 unmapped labels (of 225 total — the other 21
# already resolve via exact string match or by reusing BENCHMARK_SECTORS).
# See `_VALUATION_SECTORS_FOR_REVIEW` below for which of these are real
# judgment calls rather than obvious matches.
VALUATION_SECTORS: dict[str, str] = {
    # ---- AI / software (vertical-specific option wins over generic SaaS) ----
    "AI Chips & Hardware": "Semiconductors / Hardware",
    "AdTech Software": "Marketing / AdTech",
    "Artificial Intelligence": "AI / ML",
    "Automation & Control Systems": "Robotics / Automation",
    "Autonomous Tech": "Robotics / Automation",
    "BI & Analytics Software": "SaaS / Cloud",
    "Cloud Infrastructure": "SaaS / Cloud",
    "Communication & Collaboration Software": "SaaS / Cloud",
    "Content Management Software": "SaaS / Cloud",
    "Data Centers": "Technology",
    "Data Infrastructure": "SaaS / Cloud",
    "DeepTech": "Space / Deep Tech",
    "Design & Engineering Software": "SaaS / Cloud",
    "DevOps": "SaaS / Cloud",
    "Developer Tools": "SaaS / Cloud",
    "E-commerce Software": "SaaS / Cloud",
    "ERP Software": "SaaS / Cloud",
    "Education Software": "EdTech / Education",
    "Electronic Trading": "Fintech",
    "Energy & Utilities Software": "SaaS / Cloud",
    "Financial Data & Information": "Fintech",
    "Financial Management Software": "Fintech",
    "Financial Services Software": "Fintech",
    "Governance": "B2B Business Services",
    "Hardware": "Semiconductors / Hardware",
    "Health Data & Analytics": "Healthtech / Digital Health",
    "Healthcare Software": "Healthtech / Digital Health",
    "Human Capital Management Software": "HR / Human Capital",
    "Industrial Software": "SaaS / Cloud",
    "IT Consulting": "IT Services / Distribution",
    "IT Operations Management": "SaaS / Cloud",
    "POS & Retail Management Software": "Retail / E-Commerce",
    "Productivity Software": "SaaS / Cloud",
    "Professional Services Software": "SaaS / Cloud",
    "Public Sector & Non-Profit Software": "SaaS / Cloud",
    "Pure-Play AI Software": "AI / ML",
    "Risk & Compliance Software": "SaaS / Cloud",
    "Sales & Marketing Automation Software": "Marketing / AdTech",
    "Supply Chain Management Software": "Supply Chain / Distribution",
    "Transportation & Logistics Software": "Logistics / 3PL / Freight",
    "Travel & Hospitality Software": "Hospitality / Hotels / Tourism",
    "Video & Streaming Software": "Media / Entertainment / Gaming",
    "Vertical AI Applications": "AI / ML",
    # ---- Networking / electronics / hardware ----
    "Electrical Parts & Equipment": "Electrical Equipment",
    "Electronic Components": "Semiconductors / Hardware",
    "Electronic Equipment": "Semiconductors / Hardware",
    "Internet Service Providers": "Telecom / Connectivity",
    "Navigation & Mapping": "Technology",
    "Network Management": "SaaS / Cloud",
    "Networking Hardware": "Semiconductors / Hardware",
    "Peripherals": "Semiconductors / Hardware",
    "Satellite Communications": "Telecom / Connectivity",
    "Sensors & Instruments": "Semiconductors / Hardware",
    "Telecom Infrastructure": "Telecom / Connectivity",
    "Telecom Service Providers": "Telecom / Connectivity",
    "Wearables": "Semiconductors / Hardware",
    "Cable Service Providers": "Telecom / Connectivity",
    # ---- IoT / robotics / advanced tech ----
    "IoT": "Semiconductors / Hardware",
    "Robotics": "Robotics / Automation",
    "VR & AR": "Gaming / Metaverse",
    "3D Printing": "Industrial Manufacturing",
    "Advanced Materials": "Industrial Manufacturing",
    "Blockchain & Crypto": "Web3 / Blockchain / Digital Assets",
    # ---- Automotive / mobility / transportation ----
    "Automakers": "Automotive",
    "Automotive Parts": "Automotive",
    "Automotive Software": "Automotive",
    "Electric Vehicles": "Automotive",
    "Micromobility": "Mobility",
    "Ridesharing": "Mobility",
    "Road Transportation": "Transportation",
    "Marine Transportation": "Shipping / Maritime",
    "Railways": "Transportation",
    "Aircraft & Space Systems": "Aerospace & Defense",
    "Airports & Aviation Services": "Aviation / Aircraft Leasing",
    "Defense Systems": "Aerospace & Defense",
    "Logistics & Air Freight": "Logistics / 3PL / Freight",
    # ---- Healthcare / biotech / pharma ----
    "Bioindustrials": "Biotech / Longevity",
    "Bioinformatics": "Biotech / Longevity",
    "Biomass": "Renewable Energy / CleanTech",
    "Biopharmaceuticals": "Pharmaceuticals / Biotech",
    "Contract Research & Manufacturing": "Pharmaceuticals / Biotech",
    "Digital Therapeutics": "Healthtech / Digital Health",
    "Drug Delivery Systems": "Pharmaceuticals / Biotech",
    "Drug Development & Therapeutics": "Pharmaceuticals / Biotech",
    "EHR & Practice Management": "Healthtech / Digital Health",
    "Genomics & Personalized Medicine": "Biotech / Longevity",
    "Healthcare": "Healthcare Services / Clinics",
    "Healthtech": "Healthtech / Digital Health",
    "Hospitals & Clinics": "Healthcare Services / Clinics",
    "Laboratory Services": "Healthcare Services / Clinics",
    "Long-Term Care": "Healthcare Services / Clinics",
    "Managed Care": "Insurance / Insurtech",
    "Medical Devices": "Medical Devices & Supplies",
    "Medical Imaging & Diagnostics": "Medical Devices & Supplies",
    "Medical Supplies": "Medical Devices & Supplies",
    "Nutraceuticals & Cosmeceuticals": "Beauty & Personal Care",
    "Pharma Diagnostics & Analytics": "Pharmaceuticals / Biotech",
    "Pharmacies": "Healthcare Services / Clinics",
    "Regenerative Medicine": "Biotech / Longevity",
    "Revenue Cycle Management": "Healthtech / Digital Health",
    "Small Molecules": "Pharmaceuticals / Biotech",
    "Telemedicine & Virtual Care": "Healthtech / Digital Health",
    "Vaccines & Immunotherapies": "Pharmaceuticals / Biotech",
    "Health & Beauty": "Beauty & Personal Care",
    "Baby & Child Care": "FMCG / Consumer Goods",
    "Childcare & Early Education": "Nursery",
    # ---- Fintech / payments / financial services ----
    "B2B Payments": "Fintech",
    "BNPL": "Fintech",
    "Card Networks": "Fintech",
    "Commercial Banking": "Banking / Commercial",
    "FinTech Infrastructure": "Fintech",
    "Insurance Brokers": "Insurance / Insurtech",
    "Insurance Carriers": "Insurance / Insurtech",
    "Investment Banking": "Investment Banking / M&A Advisory",
    "Investment Brokerage": "Public Markets / Equities",
    "Lending Solutions": "Fintech",
    "Money Transfer": "Fintech",
    "Neobanking": "Fintech",
    "Neoinsurance": "Insurance / Insurtech",
    "Online Lending": "Fintech",
    "Payment Service Providers": "Fintech",
    "Payments Infrastructure": "Fintech",
    "Payments POS": "Fintech",
    # ---- Consumer / retail / e-commerce ----
    "B2B Marketplaces": "Retail / E-Commerce",
    "Classifieds": "Retail / E-Commerce",
    "Clothing & Accessories": "Luxury / Fashion / Apparel",
    "Consumer Apps": "Technology",
    "Consumer E-commerce": "Retail / E-Commerce",
    "Consumer Electronics": "Semiconductors / Hardware",
    "Consumer Marketplaces": "Retail / E-Commerce",
    "Department Stores": "Retail / E-Commerce",
    "Home & Décor": "FMCG / Consumer Goods",
    "Home Appliances": "FMCG / Consumer Goods",
    "Horizontal E-commerce": "Retail / E-Commerce",
    "Horizontal Marketplaces": "Retail / E-Commerce",
    "Loyalty & Coupons": "Marketing / AdTech",
    "Luxury Goods": "Luxury / Fashion / Apparel",
    "Price Comparison": "Retail / E-Commerce",
    "Specialty Stores": "Retail / E-Commerce",
    "Supermarkets": "Retail / E-Commerce",
    "Toys & Games": "FMCG / Consumer Goods",
    "Vertical E-commerce": "Retail / E-Commerce",
    "Vertical Marketplaces": "Retail / E-Commerce",
    "Wholesale Distribution": "Supply Chain / Distribution",
    # ---- Food / beverage / agriculture ----
    "Food & Beverages": "Food & Beverage / QSR",
    "Food Delivery": "Food & Beverage / QSR",
    "Plant-Based Food": "Food Manufacturing / FoodTech",
    "Agriculture": "Agriculture / AgriTech",
    "AgriTech": "Agriculture / AgriTech",
    # ---- Energy / industrial / materials ----
    "Chemicals": "Chemicals & Petrochemicals",
    "Energy": "Energy Infrastructure",
    "Energy Equipment": "Energy Infrastructure",
    "Energy Exploration & Generation": "Oil & Gas",
    "Energy Services": "Energy Infrastructure",
    "Energy Storage": "Energy Storage / Services",
    "Environmental & Facilities Services": "Impact / ESG / Sustainability",
    "Fossil Fuels": "Oil & Gas",
    "Building Materials": "Packaging & Materials",
    "Building Products": "Construction & Engineering",
    "Buildings & Property": "Real Estate Development",
    "Diversified Industrials": "Industrial Manufacturing",
    "Industrial Parts": "Industrial Manufacturing",
    "Machinery": "Industrial Manufacturing",
    "Metals & Mining": "Steel / Metals / Mining",
    "Packaging & Containers": "Packaging & Materials",
    "Paper & Forest Products": "Aquaculture / Forestry",
    "Solar": "Renewable Energy / CleanTech",
    "Water": "Water / Waste Management",
    "Semiconductors": "Semiconductors / Hardware",
    "Printing": "Industrial Manufacturing",
    # ---- Media / entertainment / content ----
    "Content Production": "Media / Entertainment / Gaming",
    "E-Sports": "Gaming / Metaverse",
    "Gaming - Console & PC": "Gaming / Metaverse",
    "Gaming - Mobile": "Gaming / Metaverse",
    "Music": "Creative / Arts & Culture",
    "Online Content & News": "Media / Entertainment / Gaming",
    "Publishing": "Media / Entertainment / Gaming",
    "Streaming": "Media / Entertainment / Gaming",
    "TV Broadcasting": "Media / Entertainment / Gaming",
    "Social Networks": "Media / Entertainment / Gaming",
    # ---- Travel / hospitality / leisure ----
    "Events": "Consumer & Lifestyle Services",
    "Fitness & Wellness": "Sports & Wellness",
    "Leisure & Recreation": "Sports & Wellness",
    "Online Travel": "Hospitality / Hotels / Tourism",
    "Sports": "Sports & Wellness",
    "Sports & Leisure": "Sports & Wellness",
    "Travel Services": "Hospitality / Hotels / Tourism",
    "Restaurants & Nightlife": "Food & Beverage / QSR",
    # ---- Real estate ----
    "Real Estate Services": "Property Management / Proptech",
    "Real Estate Software": "Property Management / Proptech",
    # ---- Professional / business services ----
    "Advertising & Marketing": "Marketing / AdTech",
    "BPO Services": "B2B Business Services",
    "Business Consulting": "Consulting / Advisory",
    "Future of Work": "HR / Human Capital",
    "Lead Generation": "Marketing / AdTech",
    "Learning Platforms": "EdTech / Education",
    "Market Research": "Consulting / Advisory",
    "Online Dating": "Technology",
    "Online Jobs & Recruitment": "HR / Human Capital",
    "Recruitment & Staffing": "HR / Human Capital",
    "Workspaces": "Real Estate Development",
    "Leasing & Rental Services": "B2B Business Services",
    "Tobacco": "FMCG / Consumer Goods",
    "Super App": "Technology",
}

# Real judgment calls, not obvious matches — the 85-option CRM taxonomy is
# coarser than this tool's VC/startup vocabulary, so these compress several
# distinct business models into one target, or picked between two roughly
# equally-plausible options. Worth a second look from someone with sector
# taxonomy context before these are treated as settled, the same as
# "DeepTech or hardware" above and "F&B & Hospitality" in READINESS_SECTORS.
_VALUATION_SECTORS_FOR_REVIEW: dict[str, str] = {
    k: VALUATION_SECTORS[k]
    for k in (
        "Data Centers",  # physical infra, not software — "Technology" is the generic catch-all
        "Governance",  # vague label; assumed GRC/compliance -> B2B Business Services
        "Investment Brokerage",  # could equally be Asset Management
        "Managed Care",  # US health-insurance model; Insurance/Insurtech over Healthcare Services
        "Nutraceuticals & Cosmeceuticals",  # could equally be FMCG or Pharmaceuticals/Biotech
        "Baby & Child Care",  # products (FMCG) vs the Nursery service, targeted separately
        "Building Materials",  # vs "Building Products" -> Construction & Engineering — a fine split
        "Data Infrastructure",  # could equally be "Technology" if read as physical, not software
        "Environmental & Facilities Services",  # could equally be B2B Business Services
        "Workspaces",  # co-working -> Real Estate Development, not B2B Business Services
        "Consumer Apps",  # no specific vertical fits; "Technology" is the fallback here
        "Online Dating",  # same fallback reasoning as Consumer Apps
        "Super App",  # same fallback reasoning as Consumer Apps
        "Restaurants & Nightlife",  # "Nightlife" has no target of its own; folded into F&B / QSR
        "Printing",  # a printing service, not a product — Industrial Manufacturing is a stretch
    )
}

# Merged for lookup: none of the three vocabularies' keys collide (only
# "Other" is shared between benchmark and readiness, mapping to the same
# target both times), so one combined dict is simpler than routing
# `to_sector_focus` by tool.
_MAPPED_SECTORS: dict[str, str] = {
    **BENCHMARK_SECTORS,
    **READINESS_SECTORS,
    **VALUATION_SECTORS,
}

# Vocabularies that deliberately have no mapping yet. Naming them here means
# `to_sector_focus` raises with a useful message rather than a bare KeyError,
# and the gap is visible in code rather than only in a document. Empty now
# that all three tools' own vocabularies resolve.
UNMAPPED_VOCABULARIES: tuple[str, ...] = ()


class UnmappedSectorError(ValueError):
    """Raised rather than defaulting. A wrong sector silently misfiles the
    lead and skews any sector report built on it, which is worse than a
    missing one."""

    def __init__(self, value: str) -> None:
        outstanding = (
            f" — still unmapped: {'; '.join(UNMAPPED_VOCABULARIES)}"
            if UNMAPPED_VOCABULARIES
            else ""
        )
        super().__init__(
            f"no sector_focus mapping for {value!r}. Add it to "
            f"domain/sector_mapping.py rather than defaulting{outstanding}"
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
    if raw in _MAPPED_SECTORS:
        return _MAPPED_SECTORS[raw]

    # A value that is already an option title passes through: `/enrich` picks
    # from a list that overlaps the CRM's, and the readiness form may too.
    if raw in SECTOR_FOCUS_OPTIONS:
        return raw

    lowered = raw.lower()
    for source, target in _MAPPED_SECTORS.items():
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
    unknown = sorted({t for t in _MAPPED_SECTORS.values() if t not in SECTOR_FOCUS_OPTIONS})
    if unknown:
        raise RuntimeError(f"sector_mapping targets are not live sector_focus options: {unknown}")


_assert_targets_are_live()
