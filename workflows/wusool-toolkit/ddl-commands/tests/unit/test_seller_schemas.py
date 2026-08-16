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
                "outreach_tier": "x" * 101,  # over max_length=100
                "last_attempt_outcome": "y" * 501,  # over max_length=500
            }
        )

    locs = {tuple(e["loc"]) for e in exc_info.value.errors()}
    assert ("outreach_tier",) in locs
    assert ("last_attempt_outcome",) in locs


def test_valid_input_round_trips() -> None:
    validated = SellerUpdate.model_validate(
        {"outreach_tier": "Tier 1", "est_revenue": 1_000_000.0}
    )
    assert validated.outreach_tier == "Tier 1"
    assert validated.est_revenue == 1_000_000.0


def test_everything_optional() -> None:
    validated = SellerUpdate.model_validate({})
    assert validated.outreach_tier is None
    assert validated.est_revenue is None
