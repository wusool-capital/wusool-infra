import pytest
from pydantic import ValidationError

from app.modules.ddl_commands.api.sellers import SellerUpdate


def test_collects_all_field_errors_not_fail_fast() -> None:
    """Slack's `ack(response_action="errors", ...)` is a single round trip —
    every invalid field must be reported together, not just the first one
    Pydantic happens to hit.
    """
    with pytest.raises(ValidationError) as exc_info:
        SellerUpdate.model_validate(
            {
                "outreach_tier": "x" * 101,  # over max_length=100
                "last_attempt_outcome": "y" * 501,  # over max_length=500
            }
        )

    locs = {tuple(e["loc"]) for e in exc_info.value.errors()}
    assert ("outreach_tier",) in locs
    assert ("last_attempt_outcome",) in locs


def test_valid_input_round_trips() -> None:
    validated = SellerUpdate.model_validate({"outreach_tier": "Tier 1", "est_revenue": 1_000_000.0})
    assert validated.outreach_tier == "Tier 1"
    assert validated.est_revenue == 1_000_000.0


def test_everything_optional() -> None:
    validated = SellerUpdate.model_validate({})
    assert validated.outreach_tier is None
    assert validated.est_revenue is None


def test_newer_fields_round_trip() -> None:
    validated = SellerUpdate.model_validate(
        {
            "years_active": 5,
            "funding_stage": "Bootstrapped",
            "revenue_last_full_year": 1_000_000.0,
            "revenue_year_before": 900_000.0,
            "gross_margin_pct": 42.5,
            "ebitda_deducts_salary": True,
            "annual_rent_cost": 120_000.0,
            "largest_customer_revenue_pct": 15.0,
            "repeat_revenue_pct": 60.0,
            "location_count": 3,
        }
    )
    assert validated.years_active == 5
    assert validated.funding_stage == "Bootstrapped"
    assert validated.revenue_last_full_year == 1_000_000.0
    assert validated.revenue_year_before == 900_000.0
    assert validated.gross_margin_pct == 42.5
    assert validated.ebitda_deducts_salary is True
    assert validated.annual_rent_cost == 120_000.0
    assert validated.largest_customer_revenue_pct == 15.0
    assert validated.repeat_revenue_pct == 60.0
    assert validated.location_count == 3
