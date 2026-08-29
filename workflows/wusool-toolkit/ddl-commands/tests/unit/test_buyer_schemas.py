from datetime import date

import pytest
from pydantic import ValidationError

from ddl_commands.modules.buyers.schemas import BuyerUpdate


def test_collects_all_field_errors_not_fail_fast() -> None:
    with pytest.raises(ValidationError) as exc_info:
        BuyerUpdate.model_validate(
            {
                "model": "x" * 101,  # over max_length=100
                "notes": "y" * 4001,  # over max_length=4000
            }
        )

    locs = {tuple(e["loc"]) for e in exc_info.value.errors()}
    assert ("model",) in locs
    assert ("notes",) in locs


def test_valid_input_round_trips() -> None:
    validated = BuyerUpdate.model_validate(
        {"model": "Model 1 (Network)", "profitable_only": True, "ebitda_floor": 5_000_000.0}
    )
    assert validated.model == "Model 1 (Network)"
    assert validated.profitable_only is True
    assert validated.ebitda_floor == 5_000_000.0


def test_everything_optional() -> None:
    validated = BuyerUpdate.model_validate({})
    assert validated.model is None
    assert validated.profitable_only is None


def test_newer_fields_round_trip() -> None:
    validated = BuyerUpdate.model_validate(
        {
            "ebitda_ceiling": 10_000_000.0,
            "estimated_aum": 50_000_000.0,
            "notable_investments": "Acme Co, Beta Inc",
            "relationship_warmth": "Warm",
            "target_geography": ["UAE", "Saudi Arabia"],
            "last_mandate_briefing_date": date(2026, 6, 1),
            "prior_gcc_acquisition": "Yes",
        }
    )
    assert validated.ebitda_ceiling == 10_000_000.0
    assert validated.estimated_aum == 50_000_000.0
    assert validated.notable_investments == "Acme Co, Beta Inc"
    assert validated.relationship_warmth == "Warm"
    assert validated.target_geography == ["UAE", "Saudi Arabia"]
    assert validated.last_mandate_briefing_date == date(2026, 6, 1)
    assert validated.prior_gcc_acquisition == "Yes"
