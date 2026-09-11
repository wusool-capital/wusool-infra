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

from app.modules.lead_magnets.domain.shared.sector_options import (
    SECTOR_FOCUS_OPTIONS,
    SectorFocus,
)

# The GCC SME Benchmark's established-business dropdown (20 values).
_BENCHMARK_SME = {
    "aesthetics": SectorFocus.BEAUTY_AND_PERSONAL_CARE,
    "agency": SectorFocus.MARKETING_ADTECH,
    "auto": SectorFocus.GARAGE,
    "cleaning": SectorFocus.CONSUMER_AND_LIFESTYLE_SERVICES,
    "contracting": SectorFocus.CONSTRUCTION_AND_ENGINEERING,
    "ecommerce": SectorFocus.RETAIL_E_COMMERCE,
    "fitness": SectorFocus.SPORTS_AND_WELLNESS,
    "grocery": SectorFocus.RETAIL_E_COMMERCE,
    "itservices": SectorFocus.IT_SERVICES_DISTRIBUTION,
    "laundry": SectorFocus.CONSUMER_AND_LIFESTYLE_SERVICES,
    "logistics": SectorFocus.LOGISTICS_3PL_FREIGHT,
    "manufacturing": SectorFocus.INDUSTRIAL_MANUFACTURING,
    "medical": SectorFocus.HEALTHCARE_SERVICES_CLINICS,
    "nursery": SectorFocus.NURSERY,
    "realestate": SectorFocus.RESIDENTIAL_COMMERCIAL_REAL_ESTATE,
    "restaurant": SectorFocus.FOOD_AND_BEVERAGE_QSR,
    "salon": SectorFocus.BEAUTY_AND_PERSONAL_CARE,
    "trading": SectorFocus.SUPPLY_CHAIN_DISTRIBUTION,
    "training": SectorFocus.EDTECH_EDUCATION,
    "travel": SectorFocus.HOSPITALITY_HOTELS_TOURISM,
}

# The benchmark's tech/startup dropdown. "Supply Chain or mobility" is split
# so a mobility business is not filed as distribution: both targets are live
# options, so nothing needed creating in Attio.
_BENCHMARK_TECH = {
    "AI": SectorFocus.AI_ML,
    "SaaS": SectorFocus.SAAS_CLOUD,
    "Fintech": SectorFocus.FINTECH,
    "Digital Health": SectorFocus.HEALTHTECH_DIGITAL_HEALTH,
    "Supply Chain": SectorFocus.SUPPLY_CHAIN_DISTRIBUTION,
    "Mobility": SectorFocus.MOBILITY,
    "FoodTech": SectorFocus.FOOD_MANUFACTURING_FOODTECH,
    "E-commerce": SectorFocus.RETAIL_E_COMMERCE,
    "Proptech": SectorFocus.PROPERTY_MANAGEMENT_PROPTECH,
    "Edtech": SectorFocus.EDTECH_EDUCATION,
    # Still the pre-split label. Kept so a submission from the current form,
    # before the option is split, does not raise. Remove once the form ships
    # the two separate options.
    "Supply Chain or mobility": SectorFocus.SUPPLY_CHAIN_DISTRIBUTION,
    # The other compound flagged for review; unlike mobility this one has
    # not been decided, so it keeps the source's own target.
    "DeepTech or hardware": SectorFocus.SPACE_DEEP_TECH,
    "Other": SectorFocus.DIVERSIFIED_GENERALIST,
}

BENCHMARK_SECTORS: dict[str, SectorFocus] = {**_BENCHMARK_SME, **_BENCHMARK_TECH}

# The M&A Readiness form's own dropdown (11 values, `#cSector`).
READINESS_SECTORS: dict[str, SectorFocus] = {
    "Technology & SaaS": SectorFocus.SAAS_CLOUD,
    "Healthcare & Medical": SectorFocus.HEALTHCARE_SERVICES_CLINICS,
    # Compound, like benchmark's "DeepTech or hardware": F&B is the more
    # common submission for a generalist SME assessment tool, so it is the
    # default target, not a settled decision. Flagged for the same review.
    "F&B & Hospitality": SectorFocus.FOOD_AND_BEVERAGE_QSR,
    "Professional Services": SectorFocus.CONSULTING_ADVISORY,
    "Education & Training": SectorFocus.EDTECH_EDUCATION,
    "Retail & E-Commerce": SectorFocus.RETAIL_E_COMMERCE,
    "Construction & Contracting": SectorFocus.CONSTRUCTION_AND_ENGINEERING,
    "Logistics & Supply Chain": SectorFocus.LOGISTICS_3PL_FREIGHT,
    "Financial Services": SectorFocus.FINANCIAL_SERVICES,
    "Manufacturing & Industrial": SectorFocus.INDUSTRIAL_MANUFACTURING,
    "Other": SectorFocus.DIVERSIFIED_GENERALIST,
}

# The valuation tool's own 204 unmapped labels (of 225 total — the other 21
# already resolve via exact string match or by reusing BENCHMARK_SECTORS).
# See `_VALUATION_SECTORS_FOR_REVIEW` below for which of these are real
# judgment calls rather than obvious matches.
VALUATION_SECTORS: dict[str, SectorFocus] = {
    # ---- AI / software (vertical-specific option wins over generic SaaS) ----
    "AI Chips & Hardware": SectorFocus.SEMICONDUCTORS_HARDWARE,
    "AdTech Software": SectorFocus.MARKETING_ADTECH,
    "Artificial Intelligence": SectorFocus.AI_ML,
    "Automation & Control Systems": SectorFocus.ROBOTICS_AUTOMATION,
    "Autonomous Tech": SectorFocus.ROBOTICS_AUTOMATION,
    "BI & Analytics Software": SectorFocus.SAAS_CLOUD,
    "Cloud Infrastructure": SectorFocus.SAAS_CLOUD,
    "Communication & Collaboration Software": SectorFocus.SAAS_CLOUD,
    "Content Management Software": SectorFocus.SAAS_CLOUD,
    "Data Centers": SectorFocus.TECHNOLOGY,
    "Data Infrastructure": SectorFocus.SAAS_CLOUD,
    "DeepTech": SectorFocus.SPACE_DEEP_TECH,
    "Design & Engineering Software": SectorFocus.SAAS_CLOUD,
    "DevOps": SectorFocus.SAAS_CLOUD,
    "Developer Tools": SectorFocus.SAAS_CLOUD,
    "E-commerce Software": SectorFocus.SAAS_CLOUD,
    "ERP Software": SectorFocus.SAAS_CLOUD,
    "Education Software": SectorFocus.EDTECH_EDUCATION,
    "Electronic Trading": SectorFocus.FINTECH,
    "Energy & Utilities Software": SectorFocus.SAAS_CLOUD,
    "Financial Data & Information": SectorFocus.FINTECH,
    "Financial Management Software": SectorFocus.FINTECH,
    "Financial Services Software": SectorFocus.FINTECH,
    "Governance": SectorFocus.B2B_BUSINESS_SERVICES,
    "Hardware": SectorFocus.SEMICONDUCTORS_HARDWARE,
    "Health Data & Analytics": SectorFocus.HEALTHTECH_DIGITAL_HEALTH,
    "Healthcare Software": SectorFocus.HEALTHTECH_DIGITAL_HEALTH,
    "Human Capital Management Software": SectorFocus.HR_HUMAN_CAPITAL,
    "Industrial Software": SectorFocus.SAAS_CLOUD,
    "IT Consulting": SectorFocus.IT_SERVICES_DISTRIBUTION,
    "IT Operations Management": SectorFocus.SAAS_CLOUD,
    "POS & Retail Management Software": SectorFocus.RETAIL_E_COMMERCE,
    "Productivity Software": SectorFocus.SAAS_CLOUD,
    "Professional Services Software": SectorFocus.SAAS_CLOUD,
    "Public Sector & Non-Profit Software": SectorFocus.SAAS_CLOUD,
    "Pure-Play AI Software": SectorFocus.AI_ML,
    "Risk & Compliance Software": SectorFocus.SAAS_CLOUD,
    "Sales & Marketing Automation Software": SectorFocus.MARKETING_ADTECH,
    "Supply Chain Management Software": SectorFocus.SUPPLY_CHAIN_DISTRIBUTION,
    "Transportation & Logistics Software": SectorFocus.LOGISTICS_3PL_FREIGHT,
    "Travel & Hospitality Software": SectorFocus.HOSPITALITY_HOTELS_TOURISM,
    "Video & Streaming Software": SectorFocus.MEDIA_ENTERTAINMENT_GAMING,
    "Vertical AI Applications": SectorFocus.AI_ML,
    # ---- Networking / electronics / hardware ----
    "Electrical Parts & Equipment": SectorFocus.ELECTRICAL_EQUIPMENT,
    "Electronic Components": SectorFocus.SEMICONDUCTORS_HARDWARE,
    "Electronic Equipment": SectorFocus.SEMICONDUCTORS_HARDWARE,
    "Internet Service Providers": SectorFocus.TELECOM_CONNECTIVITY,
    "Navigation & Mapping": SectorFocus.TECHNOLOGY,
    "Network Management": SectorFocus.SAAS_CLOUD,
    "Networking Hardware": SectorFocus.SEMICONDUCTORS_HARDWARE,
    "Peripherals": SectorFocus.SEMICONDUCTORS_HARDWARE,
    "Satellite Communications": SectorFocus.TELECOM_CONNECTIVITY,
    "Sensors & Instruments": SectorFocus.SEMICONDUCTORS_HARDWARE,
    "Telecom Infrastructure": SectorFocus.TELECOM_CONNECTIVITY,
    "Telecom Service Providers": SectorFocus.TELECOM_CONNECTIVITY,
    "Wearables": SectorFocus.SEMICONDUCTORS_HARDWARE,
    "Cable Service Providers": SectorFocus.TELECOM_CONNECTIVITY,
    # ---- IoT / robotics / advanced tech ----
    "IoT": SectorFocus.SEMICONDUCTORS_HARDWARE,
    "Robotics": SectorFocus.ROBOTICS_AUTOMATION,
    "VR & AR": SectorFocus.GAMING_METAVERSE,
    "3D Printing": SectorFocus.INDUSTRIAL_MANUFACTURING,
    "Advanced Materials": SectorFocus.INDUSTRIAL_MANUFACTURING,
    "Blockchain & Crypto": SectorFocus.WEB3_BLOCKCHAIN_DIGITAL_ASSETS,
    # ---- Automotive / mobility / transportation ----
    "Automakers": SectorFocus.AUTOMOTIVE,
    "Automotive Parts": SectorFocus.AUTOMOTIVE,
    "Automotive Software": SectorFocus.AUTOMOTIVE,
    "Electric Vehicles": SectorFocus.AUTOMOTIVE,
    "Micromobility": SectorFocus.MOBILITY,
    "Ridesharing": SectorFocus.MOBILITY,
    "Road Transportation": SectorFocus.TRANSPORTATION,
    "Marine Transportation": SectorFocus.SHIPPING_MARITIME,
    "Railways": SectorFocus.TRANSPORTATION,
    "Aircraft & Space Systems": SectorFocus.AEROSPACE_AND_DEFENSE,
    "Airports & Aviation Services": SectorFocus.AVIATION_AIRCRAFT_LEASING,
    "Defense Systems": SectorFocus.AEROSPACE_AND_DEFENSE,
    "Logistics & Air Freight": SectorFocus.LOGISTICS_3PL_FREIGHT,
    # ---- Healthcare / biotech / pharma ----
    "Bioindustrials": SectorFocus.BIOTECH_LONGEVITY,
    "Bioinformatics": SectorFocus.BIOTECH_LONGEVITY,
    "Biomass": SectorFocus.RENEWABLE_ENERGY_CLEANTECH,
    "Biopharmaceuticals": SectorFocus.PHARMACEUTICALS_BIOTECH,
    "Contract Research & Manufacturing": SectorFocus.PHARMACEUTICALS_BIOTECH,
    "Digital Therapeutics": SectorFocus.HEALTHTECH_DIGITAL_HEALTH,
    "Drug Delivery Systems": SectorFocus.PHARMACEUTICALS_BIOTECH,
    "Drug Development & Therapeutics": SectorFocus.PHARMACEUTICALS_BIOTECH,
    "EHR & Practice Management": SectorFocus.HEALTHTECH_DIGITAL_HEALTH,
    "Genomics & Personalized Medicine": SectorFocus.BIOTECH_LONGEVITY,
    "Healthcare": SectorFocus.HEALTHCARE_SERVICES_CLINICS,
    "Healthtech": SectorFocus.HEALTHTECH_DIGITAL_HEALTH,
    "Hospitals & Clinics": SectorFocus.HEALTHCARE_SERVICES_CLINICS,
    "Laboratory Services": SectorFocus.HEALTHCARE_SERVICES_CLINICS,
    "Long-Term Care": SectorFocus.HEALTHCARE_SERVICES_CLINICS,
    "Managed Care": SectorFocus.INSURANCE_INSURTECH,
    "Medical Devices": SectorFocus.MEDICAL_DEVICES_AND_SUPPLIES,
    "Medical Imaging & Diagnostics": SectorFocus.MEDICAL_DEVICES_AND_SUPPLIES,
    "Medical Supplies": SectorFocus.MEDICAL_DEVICES_AND_SUPPLIES,
    "Nutraceuticals & Cosmeceuticals": SectorFocus.BEAUTY_AND_PERSONAL_CARE,
    "Pharma Diagnostics & Analytics": SectorFocus.PHARMACEUTICALS_BIOTECH,
    "Pharmacies": SectorFocus.HEALTHCARE_SERVICES_CLINICS,
    "Regenerative Medicine": SectorFocus.BIOTECH_LONGEVITY,
    "Revenue Cycle Management": SectorFocus.HEALTHTECH_DIGITAL_HEALTH,
    "Small Molecules": SectorFocus.PHARMACEUTICALS_BIOTECH,
    "Telemedicine & Virtual Care": SectorFocus.HEALTHTECH_DIGITAL_HEALTH,
    "Vaccines & Immunotherapies": SectorFocus.PHARMACEUTICALS_BIOTECH,
    "Health & Beauty": SectorFocus.BEAUTY_AND_PERSONAL_CARE,
    "Baby & Child Care": SectorFocus.FMCG_CONSUMER_GOODS,
    "Childcare & Early Education": SectorFocus.NURSERY,
    # ---- Fintech / payments / financial services ----
    "B2B Payments": SectorFocus.FINTECH,
    "BNPL": SectorFocus.FINTECH,
    "Card Networks": SectorFocus.FINTECH,
    "Commercial Banking": SectorFocus.BANKING_COMMERCIAL,
    "FinTech Infrastructure": SectorFocus.FINTECH,
    "Insurance Brokers": SectorFocus.INSURANCE_INSURTECH,
    "Insurance Carriers": SectorFocus.INSURANCE_INSURTECH,
    "Investment Banking": SectorFocus.INVESTMENT_BANKING_MANDA_ADVISORY,
    "Investment Brokerage": SectorFocus.PUBLIC_MARKETS_EQUITIES,
    "Lending Solutions": SectorFocus.FINTECH,
    "Money Transfer": SectorFocus.FINTECH,
    "Neobanking": SectorFocus.FINTECH,
    "Neoinsurance": SectorFocus.INSURANCE_INSURTECH,
    "Online Lending": SectorFocus.FINTECH,
    "Payment Service Providers": SectorFocus.FINTECH,
    "Payments Infrastructure": SectorFocus.FINTECH,
    "Payments POS": SectorFocus.FINTECH,
    # ---- Consumer / retail / e-commerce ----
    "B2B Marketplaces": SectorFocus.RETAIL_E_COMMERCE,
    "Classifieds": SectorFocus.RETAIL_E_COMMERCE,
    "Clothing & Accessories": SectorFocus.LUXURY_FASHION_APPAREL,
    "Consumer Apps": SectorFocus.TECHNOLOGY,
    "Consumer E-commerce": SectorFocus.RETAIL_E_COMMERCE,
    "Consumer Electronics": SectorFocus.SEMICONDUCTORS_HARDWARE,
    "Consumer Marketplaces": SectorFocus.RETAIL_E_COMMERCE,
    "Department Stores": SectorFocus.RETAIL_E_COMMERCE,
    "Home & Décor": SectorFocus.FMCG_CONSUMER_GOODS,
    "Home Appliances": SectorFocus.FMCG_CONSUMER_GOODS,
    "Horizontal E-commerce": SectorFocus.RETAIL_E_COMMERCE,
    "Horizontal Marketplaces": SectorFocus.RETAIL_E_COMMERCE,
    "Loyalty & Coupons": SectorFocus.MARKETING_ADTECH,
    "Luxury Goods": SectorFocus.LUXURY_FASHION_APPAREL,
    "Price Comparison": SectorFocus.RETAIL_E_COMMERCE,
    "Specialty Stores": SectorFocus.RETAIL_E_COMMERCE,
    "Supermarkets": SectorFocus.RETAIL_E_COMMERCE,
    "Toys & Games": SectorFocus.FMCG_CONSUMER_GOODS,
    "Vertical E-commerce": SectorFocus.RETAIL_E_COMMERCE,
    "Vertical Marketplaces": SectorFocus.RETAIL_E_COMMERCE,
    "Wholesale Distribution": SectorFocus.SUPPLY_CHAIN_DISTRIBUTION,
    # ---- Food / beverage / agriculture ----
    "Food & Beverages": SectorFocus.FOOD_AND_BEVERAGE_QSR,
    "Food Delivery": SectorFocus.FOOD_AND_BEVERAGE_QSR,
    "Plant-Based Food": SectorFocus.FOOD_MANUFACTURING_FOODTECH,
    "Agriculture": SectorFocus.AGRICULTURE_AGRITECH,
    "AgriTech": SectorFocus.AGRICULTURE_AGRITECH,
    # ---- Energy / industrial / materials ----
    "Chemicals": SectorFocus.CHEMICALS_AND_PETROCHEMICALS,
    "Energy": SectorFocus.ENERGY_INFRASTRUCTURE,
    "Energy Equipment": SectorFocus.ENERGY_INFRASTRUCTURE,
    "Energy Exploration & Generation": SectorFocus.OIL_AND_GAS,
    "Energy Services": SectorFocus.ENERGY_INFRASTRUCTURE,
    "Energy Storage": SectorFocus.ENERGY_STORAGE_SERVICES,
    "Environmental & Facilities Services": SectorFocus.IMPACT_ESG_SUSTAINABILITY,
    "Fossil Fuels": SectorFocus.OIL_AND_GAS,
    "Building Materials": SectorFocus.PACKAGING_AND_MATERIALS,
    "Building Products": SectorFocus.CONSTRUCTION_AND_ENGINEERING,
    "Buildings & Property": SectorFocus.REAL_ESTATE_DEVELOPMENT,
    "Diversified Industrials": SectorFocus.INDUSTRIAL_MANUFACTURING,
    "Industrial Parts": SectorFocus.INDUSTRIAL_MANUFACTURING,
    "Machinery": SectorFocus.INDUSTRIAL_MANUFACTURING,
    "Metals & Mining": SectorFocus.STEEL_METALS_MINING,
    "Packaging & Containers": SectorFocus.PACKAGING_AND_MATERIALS,
    "Paper & Forest Products": SectorFocus.AQUACULTURE_FORESTRY,
    "Solar": SectorFocus.RENEWABLE_ENERGY_CLEANTECH,
    "Water": SectorFocus.WATER_WASTE_MANAGEMENT,
    "Semiconductors": SectorFocus.SEMICONDUCTORS_HARDWARE,
    "Printing": SectorFocus.INDUSTRIAL_MANUFACTURING,
    # ---- Media / entertainment / content ----
    "Content Production": SectorFocus.MEDIA_ENTERTAINMENT_GAMING,
    "E-Sports": SectorFocus.GAMING_METAVERSE,
    "Gaming - Console & PC": SectorFocus.GAMING_METAVERSE,
    "Gaming - Mobile": SectorFocus.GAMING_METAVERSE,
    "Music": SectorFocus.CREATIVE_ARTS_AND_CULTURE,
    "Online Content & News": SectorFocus.MEDIA_ENTERTAINMENT_GAMING,
    "Publishing": SectorFocus.MEDIA_ENTERTAINMENT_GAMING,
    "Streaming": SectorFocus.MEDIA_ENTERTAINMENT_GAMING,
    "TV Broadcasting": SectorFocus.MEDIA_ENTERTAINMENT_GAMING,
    "Social Networks": SectorFocus.MEDIA_ENTERTAINMENT_GAMING,
    # ---- Travel / hospitality / leisure ----
    "Events": SectorFocus.CONSUMER_AND_LIFESTYLE_SERVICES,
    "Fitness & Wellness": SectorFocus.SPORTS_AND_WELLNESS,
    "Leisure & Recreation": SectorFocus.SPORTS_AND_WELLNESS,
    "Online Travel": SectorFocus.HOSPITALITY_HOTELS_TOURISM,
    "Sports": SectorFocus.SPORTS_AND_WELLNESS,
    "Sports & Leisure": SectorFocus.SPORTS_AND_WELLNESS,
    "Travel Services": SectorFocus.HOSPITALITY_HOTELS_TOURISM,
    "Restaurants & Nightlife": SectorFocus.FOOD_AND_BEVERAGE_QSR,
    # ---- Real estate ----
    "Real Estate Services": SectorFocus.PROPERTY_MANAGEMENT_PROPTECH,
    "Real Estate Software": SectorFocus.PROPERTY_MANAGEMENT_PROPTECH,
    # ---- Professional / business services ----
    "Advertising & Marketing": SectorFocus.MARKETING_ADTECH,
    "BPO Services": SectorFocus.B2B_BUSINESS_SERVICES,
    "Business Consulting": SectorFocus.CONSULTING_ADVISORY,
    "Future of Work": SectorFocus.HR_HUMAN_CAPITAL,
    "Lead Generation": SectorFocus.MARKETING_ADTECH,
    "Learning Platforms": SectorFocus.EDTECH_EDUCATION,
    "Market Research": SectorFocus.CONSULTING_ADVISORY,
    "Online Dating": SectorFocus.TECHNOLOGY,
    "Online Jobs & Recruitment": SectorFocus.HR_HUMAN_CAPITAL,
    "Recruitment & Staffing": SectorFocus.HR_HUMAN_CAPITAL,
    "Workspaces": SectorFocus.REAL_ESTATE_DEVELOPMENT,
    "Leasing & Rental Services": SectorFocus.B2B_BUSINESS_SERVICES,
    "Tobacco": SectorFocus.FMCG_CONSUMER_GOODS,
    "Super App": SectorFocus.TECHNOLOGY,
}

# Real judgment calls, not obvious matches — the 85-option CRM taxonomy is
# coarser than this tool's VC/startup vocabulary, so these compress several
# distinct business models into one target, or picked between two roughly
# equally-plausible options. Worth a second look from someone with sector
# taxonomy context before these are treated as settled, the same as
# "DeepTech or hardware" above and "F&B & Hospitality" in READINESS_SECTORS.
_VALUATION_SECTORS_FOR_REVIEW: dict[str, SectorFocus] = {
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
_MAPPED_SECTORS: dict[str, SectorFocus] = {
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
