"""The live `organizations.sector_focus` option titles — generated.

Extracted from `ddl_commands/api/organizations.py`'s `FieldSpec`, which is
this repo's authoritative copy of the workspace's own select options and is
already covered by `test_field_specs_match_attio_registries.py`. Duplicated
here rather than imported so `domain/` does not reach into another module's
`api/` layer, and regenerated from that spec if the option set changes.

`SectorFocus` exists so `sector_mapping.py`'s ~250 mapping targets are
checked at definition time rather than at the `_assert_targets_are_live()`
import-time scan below: a misspelled `SectorFocus.FINTCH` fails to parse,
where a misspelled `"Fintch"` string literal would only be caught by that
scan (and did nothing to guard the ~250 call sites choosing between two
correctly-spelled-but-wrong options). `SECTOR_FOCUS_OPTIONS` stays a
`frozenset` over the enum, not a `frozenset[str]` retyped away — every
enum member is a `str`, so existing `value in SECTOR_FOCUS_OPTIONS` checks
elsewhere (`buyer_network.py`, `sector_mapping.py`) keep working unchanged.

Used to validate every mapping target at import: Attio rejects an undefined
select value and the live relay only logs it, so a typo would silently drop
the sector on every write.
"""

from enum import StrEnum


class SectorFocus(StrEnum):
    CLINIC = "Clinic"
    GARAGE = "Garage"
    LEGAL_SERVICES = "Legal Services"
    RETAIL_E_COMMERCE = "Retail / E-Commerce"
    UTILITIES = "Utilities"
    CREATIVE_ARTS_AND_CULTURE = "Creative / Arts & Culture"
    IT_SERVICES_DISTRIBUTION = "IT Services / Distribution"
    INDUSTRIAL_MANUFACTURING = "Industrial Manufacturing"
    PHARMACEUTICALS_BIOTECH = "Pharmaceuticals / Biotech"
    TRADE_AND_TECHNICAL_SERVICES = "Trade & Technical Services"
    PACKAGING_AND_MATERIALS = "Packaging & Materials"
    TELECOM_CONNECTIVITY = "Telecom / Connectivity"
    RESIDENTIAL_COMMERCIAL_REAL_ESTATE = "Residential / Commercial Real Estate"
    CYBERSECURITY = "Cybersecurity"
    SPORTS_AND_WELLNESS = "Sports & Wellness"
    BEAUTY_AND_PERSONAL_CARE = "Beauty & Personal Care"
    EDTECH_EDUCATION = "EdTech / Education"
    DIVERSIFIED_GENERALIST = "Diversified / Generalist"
    STEEL_METALS_MINING = "Steel / Metals / Mining"
    OIL_AND_GAS = "Oil & Gas"
    IMPACT_ESG_SUSTAINABILITY = "Impact / ESG / Sustainability"
    FINTECH = "Fintech"
    ASSET_MANAGEMENT = "Asset Management"
    AGRICULTURE_AGRITECH = "Agriculture / AgriTech"
    TECHNOLOGY = "Technology"
    LOGISTICS_3PL_FREIGHT = "Logistics / 3PL / Freight"
    ENTERPRISE_SOFTWARE = "Enterprise Software"
    BANKING_COMMERCIAL = "Banking / Commercial"
    AI_ML = "AI / ML"
    CONSTRUCTION_AND_ENGINEERING = "Construction & Engineering"
    LUXURY_FASHION_APPAREL = "Luxury / Fashion / Apparel"
    GAMING_METAVERSE = "Gaming / Metaverse"
    REAL_ASSETS = "Real Assets"
    DENTAL_SPECIALIST_CLINICS = "Dental / Specialist Clinics"
    PRIVATE_CREDIT_DEBT = "Private Credit / Debt"
    WEB3_BLOCKCHAIN_DIGITAL_ASSETS = "Web3 / Blockchain / Digital Assets"
    ENERGY_INFRASTRUCTURE = "Energy Infrastructure"
    FOOD_MANUFACTURING_FOODTECH = "Food Manufacturing / FoodTech"
    PUBLIC_MARKETS_EQUITIES = "Public Markets / Equities"
    AVIATION_AIRCRAFT_LEASING = "Aviation / Aircraft Leasing"
    CHEMICALS_AND_PETROCHEMICALS = "Chemicals & Petrochemicals"
    MEDICAL_EDUCATION = "Medical Education"
    B2B_BUSINESS_SERVICES = "B2B Business Services"
    BIOTECH_LONGEVITY = "Biotech / Longevity"
    FEMTECH_MENTAL_HEALTH = "FemTech / Mental Health"
    ELECTRICAL_EQUIPMENT = "Electrical Equipment"
    MEDICAL_DEVICES_AND_SUPPLIES = "Medical Devices & Supplies"
    HR_HUMAN_CAPITAL = "HR / Human Capital"
    HEALTHCARE_SERVICES_CLINICS = "Healthcare Services / Clinics"
    SUPPLY_CHAIN_DISTRIBUTION = "Supply Chain / Distribution"
    SAAS_CLOUD = "SaaS / Cloud"
    PROPERTY_MANAGEMENT_PROPTECH = "Property Management / Proptech"
    PRIVATE_EQUITY = "Private Equity"
    HEALTHTECH_DIGITAL_HEALTH = "Healthtech / Digital Health"
    RENEWABLE_ENERGY_CLEANTECH = "Renewable Energy / CleanTech"
    FMCG_CONSUMER_GOODS = "FMCG / Consumer Goods"
    VENTURE_GROWTH_AFRICA_MENA_SME = "Venture / Growth (Africa / MENA SME)"
    SPACE_DEEP_TECH = "Space / Deep Tech"
    MEDIA_ENTERTAINMENT_GAMING = "Media / Entertainment / Gaming"
    FAMILY_OFFICE_WEALTH_MANAGEMENT = "Family Office / Wealth Management"
    CONSULTING_ADVISORY = "Consulting / Advisory"
    MARKETING_ADTECH = "Marketing / AdTech"
    VENTURE_CAPITAL = "Venture Capital"
    REAL_ESTATE_DEVELOPMENT = "Real Estate Development"
    SHARIA_COMPLIANT = "Sharia-Compliant"
    SEMICONDUCTORS_HARDWARE = "Semiconductors / Hardware"
    ENERGY_STORAGE_SERVICES = "Energy Storage / Services"
    SHIPPING_MARITIME = "Shipping / Maritime"
    INSURANCE_INSURTECH = "Insurance / Insurtech"
    PET_CARE = "Pet Care"
    CONSUMER_AND_LIFESTYLE_SERVICES = "Consumer & Lifestyle Services"
    SOVEREIGN_WEALTH_FUND = "Sovereign Wealth Fund"
    INVESTMENT_BANKING_MANDA_ADVISORY = "Investment Banking / M&A Advisory"
    TRANSPORTATION = "Transportation"
    MOBILITY = "Mobility"
    WATER_WASTE_MANAGEMENT = "Water / Waste Management"
    AUTOMOTIVE = "Automotive"
    HOSPITALITY_HOTELS_TOURISM = "Hospitality / Hotels / Tourism"
    FOOD_AND_BEVERAGE_QSR = "Food & Beverage / QSR"
    ROBOTICS_AUTOMATION = "Robotics / Automation"
    SECURITY_SERVICES = "Security Services"
    FINANCIAL_SERVICES = "Financial Services"
    AQUACULTURE_FORESTRY = "Aquaculture / Forestry"
    AEROSPACE_AND_DEFENSE = "Aerospace & Defense"
    NURSERY = "Nursery"


SECTOR_FOCUS_OPTIONS: frozenset[str] = frozenset(SectorFocus)
