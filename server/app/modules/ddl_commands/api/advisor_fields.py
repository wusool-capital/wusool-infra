"""The fields `get_buyer` and `get_seller` return by default: what an advisor needs to
decide, not every column. Keys are the catalog's (`list_field_options`); a test checks
each one exists."""

from app.modules.ddl_commands.api.bulk_store import UploadKind

ADVISOR_FIELDS: dict[UploadKind, tuple[str, ...]] = {
    "buyer": (
        # The mandate
        "target_vertical",
        "mandate_status",
        "model",
        "investment_strategy",
        "notable_investments",
        "prior_gcc_acquisition",
        "last_mandate_briefing_date",
        # What they will buy
        "ebitda_floor",
        "ebitda_ceiling",
        "check_size_min",
        "check_size_max",
        "ev_ceiling",
        "estimated_aum",
        "deal_structure_tolerance",
        "earnout_tolerance",
        "profitable_only",
        "target_region",
        "target_country",
        # The relationship
        "relationship_warmth",
        "relationship_status",
        "last_interaction_at",
        "connection_strength",
        "deals_introduced",
        "deals_converted",
        "notes",
        # The company
        "hq_country",
        "region",
        "sector_focus",
        "client_type",
    ),
    "seller": (
        # Where the conversation stands
        "outreach_tier",
        "appetite_signal",
        "relationship_status",
        "sell_timeline",
        "readiness_score",
        "readiness_band",
        "lead_priority",
        "lead_quality_score",
        "last_attempt_date",
        "last_attempt_channel",
        "last_attempt_outcome",
        "re_engage_date",
        # The financials
        "est_revenue",
        "est_ebitda",
        "ebitda_adjusted",
        "owner_salary",
        "valuation_low",
        "valuation_mid",
        "valuation_high",
        "implied_ev_low",
        "implied_ev_high",
        "revenue_last_full_year",
        "revenue_year_before",
        "gross_margin_pct",
        "annual_rent_cost",
        "largest_customer_revenue_pct",
        "repeat_revenue_pct",
        "years_active",
        "headcount",
        "location_count",
        "funding_stage",
        # The benchmark result
        "benchmark_score",
        "benchmark_band",
        "benchmark_quartile",
        "headline_flag",
        "recommended_referral",
        # The relationship and the company
        "last_interaction_at",
        "connection_strength",
        "hq_country",
        "region",
        "sector_focus",
        "client_type",
    ),
}
