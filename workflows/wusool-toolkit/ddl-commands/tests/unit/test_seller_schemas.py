import pytest
from pydantic import ValidationError

from ddl_commands.modules.sellers.schemas import SellerUpdate


def test_collects_all_field_errors_not_fail_fast() -> None:
    """Slack's `ack(response_action="errors", ...)` is a single round trip —
    every invalid field must be reported together, not just the first one
    Pydantic happens to hit.
    """
    with pytest.raises(ValidationError) as exc_info:
        SellerUpdate.model_validate(
            {
                "readiness_score": 150,  # over the 0-100 ceiling
                "lead_quality_score": -5,  # under the 0 floor
                "est_revenue": {"amount": 100, "currency": "usd"},  # lowercase, invalid
            }
        )

    locs = {tuple(e["loc"]) for e in exc_info.value.errors()}
    assert ("readiness_score",) in locs
    assert ("lead_quality_score",) in locs
    assert ("est_revenue", "currency") in locs


def test_valid_input_round_trips() -> None:
    validated = SellerUpdate.model_validate(
        {
            "outreach_tier": "warm",
            "readiness_score": 75,
            "est_revenue": {"amount": 1_000_000, "currency": "AED"},
        }
    )
    assert validated.outreach_tier == "warm"
    assert validated.readiness_score == 75
    assert validated.est_revenue is not None
    assert validated.est_revenue.currency == "AED"


def test_everything_optional() -> None:
    validated = SellerUpdate.model_validate({})
    assert validated.outreach_tier is None
    assert validated.readiness_score is None
